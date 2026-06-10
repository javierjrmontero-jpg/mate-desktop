"""
MATE Wake Word — Paso 2: Entrenar modelo "Oye MATE"
====================================================
Entrena un clasificador binario sobre las muestras generadas en el paso 1,
usando el extractor de features de OpenWakeWord (embeddings de audio).

El resultado es un modelo ONNX listo para usar en el servicio.

Ejecutar:
    python 02_train_model.py

Tiempo estimado: 5-20 min en CPU según cantidad de muestras.
"""

import os
import glob
import numpy as np
from pathlib import Path
import onnxruntime as ort

# ─── Configuración ────────────────────────────────────────────────────────────
POSITIVE_DIR  = Path("samples/positive")
NEGATIVE_DIR  = Path("samples/negative") 
MODEL_OUTPUT  = Path("models/oye_mate.onnx")
MODEL_OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# Parámetros de entrenamiento
EPOCHS        = 200
LEARNING_RATE = 0.001
BATCH_SIZE    = 32
TEST_SPLIT    = 0.15

# Ventana temporal que evaluará el modelo en producción.
# openwakeword.Model lee esto directamente de la forma de entrada del ONNX
# (.get_inputs()[0].shape[1]) y le pasa exactamente N_FRAMES embeddings
# consecutivos en cada predicción — por eso el dataset de entrenamiento debe
# tener EXACTAMENTE esta forma por muestra: (N_FRAMES, EMBED_DIM).
N_FRAMES  = 16   # 16 × 80 ms ≈ 1.28 s de contexto (suficiente para "Oye MATE")
EMBED_DIM = 96   # fijo por el modelo de embeddings de OpenWakeWord
# ──────────────────────────────────────────────────────────────────────────────


def load_wav_16k(path: str) -> np.ndarray:
    """Carga un WAV como array float32 a 16kHz."""
    import wave, struct
    with wave.open(path, 'rb') as wf:
        assert wf.getnchannels() == 1, f"Debe ser mono: {path}"
        assert wf.getframerate() == 16000, f"Debe ser 16kHz: {path}"
        raw = wf.readframes(wf.getnframes())
        samples = struct.unpack(f"{wf.getnframes()}h", raw)
        return np.array(samples, dtype=np.float32) / 32768.0


def extract_features_oww(audio: np.ndarray, audio_features) -> np.ndarray:
    """
    Extrae embeddings de audio usando el extractor oficial de OpenWakeWord
    (AudioFeatures.embed_clips — la misma función que usan sus notebooks
    de entrenamiento; NO existe un método 'embed_clip' singular en la API).

    embed_clips() exige:
      - audio en PCM int16 (no float normalizado)
      - un batch 2D de forma (N, samples)
      - clips de al menos ~0.8s (76 frames de melspectrograma); los más
        cortos generan ValueError y se descartan (quedan en "sin features")

    Retorna un array (frames, 96): un vector de 96 dims por ventana temporal.
    """
    try:
        pcm16 = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
        batch = pcm16[None, :]  # embed_clips espera (N, samples)
        emb = audio_features.embed_clips(x=batch, batch_size=1)
        return np.array(emb[0])  # (frames, 96) del único clip del batch
    except Exception:
        return np.array([])


def _fit_window(feats: np.ndarray, n_frames: int = N_FRAMES) -> np.ndarray:
    """
    Ajusta los embeddings (frames, 96) de un clip a una ventana fija de
    `n_frames`, alineada al FINAL del clip — igual que OpenWakeWord alinea
    sus propios clips positivos de entrenamiento — para que el modelo
    aprenda a puntuar alto justo cuando termina de pronunciarse "Oye MATE".

    Clips más cortos se rellenan con ceros al inicio (padding); más largos
    se recortan por el principio, conservando el final.

    Retorna siempre (n_frames, 96).
    """
    if feats.shape[0] >= n_frames:
        return feats[-n_frames:]
    pad = np.zeros((n_frames - feats.shape[0], feats.shape[1]), dtype=feats.dtype)
    return np.vstack([pad, feats])


# Paso entre ventanas deslizantes para negativos: 4 frames ≈ 320ms.
NEGATIVE_WINDOW_STRIDE = 4


def _sliding_windows(feats: np.ndarray, n_frames: int = N_FRAMES,
                     stride: int = NEGATIVE_WINDOW_STRIDE) -> list:
    """
    Genera TODAS las ventanas (n_frames, 96) posibles deslizando sobre `feats`
    con paso `stride`. A diferencia de _fit_window (una sola ventana fija por
    clip), esto produce muchas ventanas continuas y solapadas — exactamente
    el tipo de entrada que openwakeword.Model evalúa en producción cada 80ms.

    Usar SOLO para negativos: entrenar con muchas ventanas reales de "esto
    NO es la wake word" es lo que más reduce los falsos positivos en stream
    continuo (el modelo nunca veía este tipo de ventana "intermedia" antes).
    """
    n = feats.shape[0]
    if n < n_frames:
        return [_fit_window(feats, n_frames)]
    return [feats[start:start + n_frames] for start in range(0, n - n_frames + 1, stride)]


def prepare_dataset():
    """
    Carga muestras positivas y negativas, extrae features, retorna X, y.
    """
    from openwakeword.utils import AudioFeatures

    print("🔧 Cargando extractor de features de OpenWakeWord (AudioFeatures)...")
    # AudioFeatures calcula los embeddings (melspectrograma + modelo de embedding)
    # que luego alimentan al clasificador final — es el mismo paso que usa
    # OpenWakeWord internamente antes de pasar por el modelo de wake word.
    audio_features = AudioFeatures()

    positive_files = glob.glob(str(POSITIVE_DIR / "*.wav"))
    negative_files = glob.glob(str(NEGATIVE_DIR / "*.wav")) if NEGATIVE_DIR.exists() else []

    if not positive_files:
        raise FileNotFoundError(f"No se encontraron muestras positivas en '{POSITIVE_DIR}'. "
                                "Ejecutar primero 01_generate_samples.py")

    print(f"📊 Muestras: {len(positive_files)} positivas | {len(negative_files)} negativas")

    if not negative_files:
        print("⚠️  No hay muestras negativas locales. "
              "Descargando dataset de negativos de OpenWakeWord...")
        _download_negative_samples()
        negative_files = glob.glob(str(NEGATIVE_DIR / "*.wav"))

    X, y = [], []

    # Positivas
    print("  Procesando muestras positivas...")
    pos_ok, pos_fail, pos_empty = 0, 0, 0
    for i, f in enumerate(positive_files):
        try:
            audio = load_wav_16k(f)
            feats = extract_features_oww(audio, audio_features)
            if feats.size > 0:
                X.append(_fit_window(feats))  # ventana fija (N_FRAMES, 96), alineada al final
                y.append(1)
                pos_ok += 1
            else:
                pos_empty += 1
        except Exception as e:
            pos_fail += 1
            if pos_fail <= 3:
                print(f"    ⚠️  {f}: {e}")
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(positive_files)}", end="\r")
    print(f"\n  → Positivas: {pos_ok} OK | {pos_empty} sin features | {pos_fail} con error")

    # Negativas: usamos TODOS los clips disponibles (sin truncar a len(positivas)).
    # Cada clip genera VARIAS ventanas deslizantes (no una sola fija al final) para
    # que el clasificador vea el mismo tipo de entrada "intermedia" que evalúa en
    # producción cada 80ms — esto es lo que reduce los falsos positivos por
    # desajuste train/inferencia (ver _sliding_windows). El desbalance resultante
    # (más ventanas negativas que positivas) lo compensa
    # LogisticRegression(class_weight="balanced") en train_classifier().
    print(f"  Procesando {len(negative_files)} clips negativos "
          f"(ventanas deslizantes, stride={NEGATIVE_WINDOW_STRIDE})...")
    neg_ok, neg_fail, neg_empty, neg_windows = 0, 0, 0, 0
    for i, f in enumerate(negative_files):
        try:
            audio = load_wav_16k(f)
            feats = extract_features_oww(audio, audio_features)
            if feats.size > 0:
                windows = _sliding_windows(feats)
                for w in windows:
                    X.append(w)
                    y.append(0)
                neg_windows += len(windows)
                neg_ok += 1
            else:
                neg_empty += 1
        except Exception as e:
            neg_fail += 1
            if neg_fail <= 3:
                print(f"    ⚠️  {f}: {e}")
        if (i + 1) % 50 == 0:
            print(f"    {i+1}/{len(negative_files)}", end="\r")
    print(f"\n  → Negativas: {neg_ok} clips OK ({neg_windows} ventanas generadas) "
          f"| {neg_empty} sin features | {neg_fail} con error")

    # X: (num_muestras, N_FRAMES, EMBED_DIM) — ventanas temporales fijas,
    # NO vectores promediados. Esta es la forma que openwakeword.Model espera
    # entregar en cada predicción (ver Model.predict → preprocessor.get_features).
    return np.array(X, dtype=np.float32), np.array(y, dtype=np.float32)


def _download_negative_samples():
    """Descarga una selección de muestras negativas del repo de OpenWakeWord."""
    import urllib.request, zipfile, io
    NEGATIVE_DIR.mkdir(parents=True, exist_ok=True)
    url = "https://github.com/dscripka/openWakeWord/releases/download/v0.5.1/negative_samples.zip"
    print(f"  Descargando de {url}...")
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            z.extractall(NEGATIVE_DIR)
        print(f"  ✅ Negativos descargados en '{NEGATIVE_DIR}'")
    except Exception as e:
        print(f"  ❌ No se pudo descargar automáticamente: {e}")
        print(f"  → Descargá manualmente y extraé en '{NEGATIVE_DIR}'")


def train_classifier(X: np.ndarray, y: np.ndarray):
    """
    Entrena (StandardScaler + LogisticRegression) sobre ventanas temporales de
    embeddings (N_FRAMES, 96) y exporta TODO el pipeline a un único ONNX
    con la interfaz exacta que openwakeword.Model.predict() necesita:

        entrada  "float_input"  : float32 (lote, N_FRAMES, 96)  ← embeddings crudos
        salida   "wakeword_score": float32 (lote, 1)            ← score [0,1]

    Empaquetar el escalado DENTRO del grafo ONNX (vía sklearn Pipeline) evita
    depender de un scaler.json aplicado a mano en 03_service.py — antes se
    guardaba ese archivo pero el servicio nunca lo leía (bug latente).
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from skl2onnx import convert_sklearn
    from skl2onnx.common.data_types import FloatTensorType
    import onnx
    from onnx import helper, TensorProto, numpy_helper

    n_samples, n_frames, embed_dim = X.shape
    X_flat = X.reshape(n_samples, n_frames * embed_dim)  # sklearn solo admite 2D

    print(f"\n🧠 Entrenando clasificador ({n_samples} muestras, ventana {n_frames}×{embed_dim})...")

    X_train, X_test, y_train, y_test = train_test_split(
        X_flat, y, test_size=TEST_SPLIT, random_state=42, stratify=y
    )

    # LogisticRegression (modelo lineal) en vez de MLP: con ~850 muestras y
    # 1536 dimensiones de entrada, el MLP memorizaba el dataset y producía
    # un comportamiento "interruptor" (score saltando entre 0.000 y 0.99,
    # sin valores intermedios — visto en vivo con el debug de 03_service.py).
    # Un modelo lineal con regularización fuerte tiene mucha menos capacidad
    # de sobreajustar y da probabilidades suaves y mejor calibradas.
    pipeline = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            C=0.05,              # inverso de la regularización: bajo = más regularización
            max_iter=2000,
            class_weight="balanced",
            random_state=42,
        )),
    ])
    pipeline.fit(X_train, y_train)

    acc = pipeline.score(X_test, y_test)
    print(f"\n✅ Accuracy en test: {acc:.2%}")

    clf = pipeline.named_steps["clf"]

    # ── Exportar el PIPELINE completo (scaler + MLP) a ONNX ───────────────────
    # OpenWakeWord (Model.__init__) exige que el modelo wakeword tenga UNA sola
    # salida tensor de forma (lote, n_clases) — lee .get_outputs()[0].shape[1].
    # skl2onnx, por defecto, genera DOS salidas para un clasificador binario:
    #   - output_label: tensor 1D (N,)            ← .shape[1] no existe → IndexError
    #   - output_probability: ZipMap (no es tensor)
    # Esto producía "IndexError: list index out of range" al cargar el modelo.
    #
    # Arreglo: zipmap=False → probabilidad como tensor (N, 2) + nodo Gather que
    # selecciona la columna de la clase positiva ("1" = wake word presente),
    # dejando una única salida (N, 1) — igual que los modelos de OpenWakeWord.
    initial_type = [("flat_input", FloatTensorType([None, n_frames * embed_dim]))]
    onnx_model = convert_sklearn(
        pipeline, initial_types=initial_type,
        options={id(clf): {"zipmap": False}},
    )

    graph = onnx_model.graph
    flat_input_name = graph.input[0].name  # nombre que espera el primer nodo del pipeline

    # El nombre de la salida de probabilidades varía según la versión de
    # skl2onnx. La identificamos por su TIPO: tensor float de rango 2
    # (N, n_clases) — a diferencia de "output_label" (int64, rango 1).
    prob_tensor = None
    for o in graph.output:
        t = o.type.tensor_type
        if t.elem_type == TensorProto.FLOAT and len(t.shape.dim) == 2:
            prob_tensor = o.name
            break
    if prob_tensor is None:
        outs = [(o.name, o.type.tensor_type.elem_type, len(o.type.tensor_type.shape.dim)) for o in graph.output]
        raise RuntimeError(f"No se encontró la salida de probabilidades (float, rango 2). Salidas del grafo: {outs}")

    positive_idx = int(np.where(clf.classes_ == 1)[0][0])
    idx_init = helper.make_tensor("wakeword_class_idx", TensorProto.INT64, [1], [positive_idx])
    graph.initializer.append(idx_init)
    graph.node.append(helper.make_node(
        "Gather",
        inputs=[prob_tensor, "wakeword_class_idx"],
        outputs=["wakeword_score"],
        axis=1,
        name="select_positive_class",
    ))

    # ── Adaptador de entrada 3D → 2D ──────────────────────────────────────────
    # openwakeword.Model.predict() entrega ventanas 3D (lote, N_FRAMES, 96)
    # (ver self.preprocessor.get_features(N_FRAMES)), pero el pipeline de
    # sklearn/skl2onnx solo acepta 2D (lote, N_FRAMES*96). Envolvemos el grafo
    # con una nueva entrada 3D pública "float_input" + un nodo Reshape que la
    # aplana antes de entrar al pipeline original.
    new_input = helper.make_tensor_value_info(
        "float_input", TensorProto.FLOAT, [None, n_frames, embed_dim]
    )
    shape_init = numpy_helper.from_array(
        np.array([-1, n_frames * embed_dim], dtype=np.int64), name="flatten_shape"
    )
    graph.initializer.append(shape_init)
    graph.node.insert(0, helper.make_node(
        "Reshape",
        inputs=["float_input", "flatten_shape"],
        outputs=[flat_input_name],
        name="flatten_window",
    ))

    del graph.input[:]
    graph.input.append(new_input)
    del graph.output[:]
    graph.output.append(helper.make_tensor_value_info("wakeword_score", TensorProto.FLOAT, [None, 1]))

    onnx.checker.check_model(onnx_model)

    MODEL_OUTPUT.write_bytes(onnx_model.SerializeToString())
    print(f"💾 Modelo guardado: {MODEL_OUTPUT}")
    print(f"   Entrada: (lote, {n_frames}, {embed_dim}) | Salida: (lote, 1) — listo para openwakeword.Model")

    return acc


def main():
    # Verificar dependencias extra
    missing = []
    for pkg in ["sklearn", "skl2onnx"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        print("❌ Faltan dependencias de entrenamiento. Instalar:")
        print(f"   pip install scikit-learn skl2onnx")
        return

    X, y = prepare_dataset()
    if len(X) < 10:
        print("❌ No hay suficientes muestras para entrenar. Verificar el paso 1.")
        return

    acc = train_classifier(X, y)

    if acc >= 0.90:
        print(f"\n🎉 Modelo listo con {acc:.1%} de precisión.")
        print(f"➡  Siguiente paso: python 03_service.py")
    else:
        print(f"\n⚠️  Precisión baja ({acc:.1%}). Recomendaciones:")
        print("   - Generar más muestras positivas (reejecutar 01_generate_samples.py)")
        print("   - Agregar grabaciones propias de tu voz en samples/positive/")
        print("   - Verificar que las muestras negativas sean variadas")


if __name__ == "__main__":
    main()
