import ctypes, sys, wave, espeakng_loader as L
lib = ctypes.CDLL(L.get_library_path())
buf = bytearray()
CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
def cb(w, n, e):
    if n > 0: buf.extend(ctypes.string_at(w, n*2))
    return 0
cbf = CB(cb)
rate = lib.espeak_Initialize(2, 0, L.get_data_path().encode(), 0)
lib.espeak_SetSynthCallback(cbf)
lib.espeak_SetVoiceByName(b"ar")
lib.espeak_SetParameter(1, 135, 0)  # rate
lib.espeak_SetParameter(3, 38, 0)   # pitch (lower)
def say(text, out):
    buf.clear()
    t = text.encode()
    lib.espeak_Synth(t, len(t)+1, 0, 0, 0, 0x1, None, None)  # CHARS_UTF8
    lib.espeak_Synchronize()
    w = wave.open(out, 'wb'); w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(bytes(buf)); w.close()
if __name__ == "__main__":
    say(sys.argv[1], sys.argv[2]); print(rate, len(buf))
