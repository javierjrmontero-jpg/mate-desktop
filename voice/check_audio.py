import sounddevice as sd

print("=== HOST APIs ===")
for i, api in enumerate(sd.query_hostapis()):
    print(f"  [{i}] {api['name']} — default_input: {api['default_input_device']}")

print("\n=== INPUT DEVICES ===")
for i, dev in enumerate(sd.query_devices()):
    if dev['max_input_channels'] > 0:
        api_name = sd.query_hostapis(dev['hostapi'])['name']
        print(f"  [{i}] {dev['name']} | API: {api_name} | ch: {dev['max_input_channels']}")

print(f"\n=== DEFAULT ===")
print(f"  {sd.default.device}")
