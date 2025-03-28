# spotify_shannon.py

class Shannon:
    def __init__(self, key: bytes):
        self.sbuf = [0] * 16
        self.r = [0] * 16
        self.key(key)

    def key(self, key: bytes):
        for i in range(len(key)):
            self.r[i % 16] ^= key[i]
        self.cycle()

    def cycle(self):
        t = [0] * 16
        for i in range(16):
            t[i] = self.r[(i - 1) % 16]
        for i in range(16):
            self.r[i] = (t[i] ^ (self.r[i] >> 3) ^ (self.r[(i - 1) % 16] << 5)) & 0xFFFFFFFF
        self.sbuf = self.r.copy()

    def nonce(self, nonce: bytes):
        self.r[0] ^= int.from_bytes(nonce, 'big')
        self.cycle()

    def encrypt(self, plaintext: bytes) -> bytes:
        self.cycle()
        return bytes([b ^ (self.sbuf[i % 16] & 0xFF) for i, b in enumerate(plaintext)])

    def decrypt(self, ciphertext: bytes) -> bytes:
        return self.encrypt(ciphertext)

    def finish(self) -> bytes:
        return bytes([sum(self.sbuf) & 0xFF] * 4)  # Dummy MAC


class SpotifyShannon:
    def __init__(self, send_key: bytes, recv_key: bytes):
        self.send_cipher = Shannon(send_key)
        self.recv_cipher = Shannon(recv_key)
        self.send_nonce = 0
        self.recv_nonce = 0

    def _make_nonce(self, counter: int) -> bytes:
        return counter.to_bytes(4, byteorder='big')

    def encrypt_packet(self, plaintext: bytes) -> bytes:
        nonce = self._make_nonce(self.send_nonce)
        self.send_cipher.nonce(nonce)
        self.send_nonce += 1

        ciphertext = self.send_cipher.encrypt(plaintext)
        mac = self.send_cipher.finish()
        return plaintext[:1] + len(plaintext[1:]).to_bytes(2, 'big') + ciphertext[1:] + mac

    def decrypt_packet(self, data: bytes) -> bytes:
        nonce = self._make_nonce(self.recv_nonce)
        self.recv_cipher.nonce(nonce)
        self.recv_nonce += 1

        cmd = data[0:1]
        length = int.from_bytes(data[1:3], 'big')
        payload = data[3:-4]
        mac = data[-4:]

        decrypted = self.recv_cipher.decrypt(cmd + payload)
        calc_mac = self.recv_cipher.finish()

        if mac != calc_mac:
            raise ValueError("Shannon MAC mismatch")

        return decrypted
