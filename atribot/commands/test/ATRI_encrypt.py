
from math import floor
from typing import Union


class Encrypt:
    """
    修复版 - 基于Unicode特殊字符的编码器
    """

    cr = "ĀāĂăĄąÀÁÂÃÄÅ"
    cc = "ŢţŤťŦŧṪṫṬṭṮṯṰṱ"
    cn = "ŔŕŘřṘṙŖŗȐȑȒȓṚṛṜṝṞṟɌɍⱤɽᵲᶉɼɾᵳʀＲｒ"
    cb = "ĨĩĪīĬĭĮįİı"

    sr = len(cr)
    sc = len(cc)
    sn = len(cn)
    sb = len(cb)
    src = sr * sc
    snb = sn * sb
    scnb = sc * snb

    def _div(self, a: int, b: int) -> int:
        return floor(a / b)

    def _encodeByte(self, i) -> Union[str, None]:
        if i > 0xFF:
            raise ValueError("ERROR! at/ri overflow")

        if i > 0x7F:
            i = i & 0x7F
            return self.cn[self._div(i, self.sb)] + self.cb[i % self.sb]

        return self.cr[self._div(i, self.sc)] + self.cc[i % self.sc]

    def _encodeShort(self, i) -> str:
        if i > 0xFFFF:
            raise ValueError("ERROR! atri overflow")

        reverse = False
        if i > 0x7FFF:
            reverse = True
            i = i & 0x7FFF

        char = [
            self._div(i, self.scnb),
            self._div(i % self.scnb, self.snb),
            self._div(i % self.snb, self.sb),
            i % self.sb,
        ]
        char = [self.cr[char[0]], self.cc[char[1]], self.cn[char[2]], self.cb[char[3]]]

        if reverse:
            return char[2] + char[3] + char[0] + char[1]

        return "".join(char)

    def _decodeByte(self, c) -> int:
        if len(c) != 2:
            raise ValueError("ERROR! byte length must be 2")
            
        nb = False
        try:
            idx0 = self.cn.index(c[0])
            idx1 = self.cb.index(c[1])
            nb = True
        except ValueError:
            try:
                idx0 = self.cr.index(c[0])
                idx1 = self.cc.index(c[1])
                nb = False
            except ValueError:
                raise ValueError("ERROR! invalid byte characters")

        if nb:
            result = idx0 * self.sb + idx1
            if result > 0x7F:
                raise ValueError("ERROR! at/ri overflow")
            return result | 0x80
        else:
            result = idx0 * self.sc + idx1
            if result > 0x7F:
                raise ValueError("ERROR! at/ri overflow")
            return result

    def _decodeShort(self, c) -> int:
        if len(c) != 4:
            raise ValueError("ERROR! short length must be 4")
            
        reverse = c[0] not in self.cr
        try:
            if not reverse:
                idx = [
                    self.cr.index(c[0]),
                    self.cc.index(c[1]),
                    self.cn.index(c[2]),
                    self.cb.index(c[3]),
                ]
            else:
                idx = [
                    self.cr.index(c[2]),
                    self.cc.index(c[3]),
                    self.cn.index(c[0]),
                    self.cb.index(c[1]),
                ]
        except ValueError:
            raise ValueError("ERROR! not atri")

        result = idx[0] * self.scnb + idx[1] * self.snb + idx[2] * self.sb + idx[3]
        if result > 0x7FFF:
            raise ValueError("ERROR! atri overflow")

        result |= 0x8000 if reverse else 0
        return result

    def _encodeBytes(self, b) -> str:
        result = []
        # 每2个字节编码为4个字符
        for i in range(0, len(b) >> 1):
            short_val = (b[i * 2] << 8) | b[i * 2 + 1]
            result.append(self._encodeShort(short_val))

        # 如果奇数长度，最后一个字节单独编码
        if len(b) & 1:
            result.append(self._encodeByte(b[-1]))

        return "".join(result)

    def encode(self, s: str, encoding: str = "utf-8"):
        if not isinstance(s, str):
            raise ValueError("Please enter str instead of other")

        return self._encodeBytes(s.encode(encoding))

    def _decodeBytes(self, s: str):
        if not isinstance(s, str):
            raise ValueError("Please enter str instead of other")

        result = bytearray()
        i = 0
        while i < len(s):
            # 检查剩余长度
            remaining = len(s) - i
            if remaining >= 4:
                # 尝试解码4字符（Short）
                try:
                    short_val = self._decodeShort(s[i:i+4])
                    result.append((short_val >> 8) & 0xFF)
                    result.append(short_val & 0xFF)
                    i += 4
                    continue
                except ValueError:
                    pass
            
            if remaining >= 2:
                # 解码2字符（Byte）
                byte_val = self._decodeByte(s[i:i+2])
                result.append(byte_val)
                i += 2
            else:
                raise ValueError("ERROR: invalid length or characters")

        return bytes(result)

    def decode(self, s: str, encoding: str = "utf-8") -> str:
        if not isinstance(s, str):
            raise ValueError("Please enter str instead of other")

        try:
            return self._decodeBytes(s).decode(encoding)
        except UnicodeDecodeError:
            raise ValueError("Decoding failed")

