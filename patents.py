import re
from datetime import datetime
from xml.etree import ElementTree

import httpx

BASE = "https://data.epo.org/publication-server/rest/v1.2/patents"
EXAMPLE = "EP1004359B1"


def normalize(text):
    value = re.sub(r"[\s-]+", "", text.upper())
    match = re.fullmatch(r"EP([0-9]{7})(?:NW)?([AB][0-9])", value)
    if not match:
        raise ValueError("Введите номер европейской публикации целиком, например EP1004359B1.")
    digits, kind = match.groups()
    return f"EP{digits}NW{kind}"


async def lookup(text, detailed):
    key = normalize(text)
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(f"{BASE}/{key}/document.xml")
        if response.status_code == 404:
            return "EPO не нашло XML для этого номера. Проверьте цифры и код публикации."
        response.raise_for_status()
    root = ElementTree.fromstring(response.content)
    if root.tag != "ep-patent-document":
        return "EPO вернуло ответ без карточки патента."
    titles = root.findall(".//B542")
    title = next(iter(titles), None)
    for group in root.iter("B540"):
        language = ""
        for field in group:
            if field.tag == "B541":
                language = field.text
            elif field.tag == "B542" and language == "en":
                title = field
                break
    name = "".join(title.itertext()).strip() if title is not None else "Название отсутствует"
    number = key.replace("NW", "")
    lines = [number, name[:700]]
    if detailed:
        date = root.get("date-publ", "")
        try:
            date = datetime.strptime(date, "%Y%m%d").strftime("%d.%m.%Y")
        except ValueError:
            date = "не указана"
        lines.extend([f"Дата публикации: {date}", f"Код вида документа: {key[-2:]}"])
    lines.append(f"{BASE}/{key}/document.pdf")
    return "\n".join(lines)

