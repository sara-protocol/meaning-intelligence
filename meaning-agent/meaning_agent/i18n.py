"""Small bilingual helpers shared by deterministic skills and interfaces."""


def bi(zh, en):
    return {"zh": str(zh), "en": str(en)}


def pick(value, language="zh"):
    if isinstance(value, dict):
        return value.get(language) or value.get("en") or value.get("zh") or ""
    return str(value)


def text_language(text):
    zh = sum("\u4e00" <= char <= "\u9fff" for char in text)
    en = sum(char.isalpha() and char.isascii() for char in text)
    return "zh" if zh >= en else "en"


def question(zh, en, language="zh"):
    return {"zh": zh, "en": en, "preferred": language}
