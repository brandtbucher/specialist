def encode_decode(key: str, text: str) -> str:
    out = []
    for i, t in enumerate(text):
        k = key[i % len(key)]
        out.append(chr(ord(t) ^ ord(k)))
    return "".join(out)

if __name__ == "__main__":
    key = "Spam"
    text = "Hello, world!"
    encoded = encode_decode(key, text)
    decoded = encode_decode(key, encoded)
    assert decoded == text
