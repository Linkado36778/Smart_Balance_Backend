"""Populate the database with foods from the TACO spreadsheet."""

from pathlib import Path, PurePosixPath
import zipfile
import xml.etree.ElementTree as ET

from application.models.application_models import (
    Category,
    Food,
    FoodNutrientAssociation,
    Nutrient,
)
from shared.database import SESSEON_LOCAL, initialize_database


SPREADSHEET_PATH = Path(__file__).parent / "Tabela_nutricional_TACO.xlsx"

XML_NS = {
    "a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
}

NUTRIENT_COLUMNS = {
    "Proteínas (g)": "Proteinas",
    "Carboidratos (g)": "Carboidratos",
    "Gorduras (g)": "Gorduras",
    "Fibras (g)": "Fibras",
    "Sódio (mg)": "Sodio",
    "Potássio (mg)": "Potassio",
    "Cálcio (mg)": "Calcio",
    "Ferro (mg)": "Ferro",
    "Vitamina C (mg)": "Vitamina C",
}


def column_index(cell_reference: str) -> int:
    """Convert an Excel cell reference like A1 or AB4 to a zero-based column index."""
    letters = "".join(character for character in cell_reference if character.isalpha())
    index = 0
    for letter in letters:
        index = index * 26 + ord(letter.upper()) - 64
    return index - 1


def resolve_xlsx_target(target: str) -> str:
    """Resolve workbook relationship targets to zip member paths."""
    target = target.lstrip("/")
    if target.startswith("xl/"):
        return target
    return str(PurePosixPath("xl") / target)


def parse_cell_value(cell: ET.Element, shared_strings: list[str]) -> str | None:
    """Return a cell value, resolving shared string references."""
    value = cell.find("a:v", XML_NS)
    if value is None:
        return None

    cell_value = value.text
    if cell.attrib.get("t") == "s" and cell_value is not None:
        return shared_strings[int(cell_value)]
    return cell_value


def read_shared_strings(workbook_zip: zipfile.ZipFile) -> list[str]:
    """Read shared strings from an XLSX archive."""
    if "xl/sharedStrings.xml" not in workbook_zip.namelist():
        return []

    root = ET.fromstring(workbook_zip.read("xl/sharedStrings.xml"))
    return [
        "".join(text.text or "" for text in item.findall(".//a:t", XML_NS))
        for item in root.findall("a:si", XML_NS)
    ]


def read_rows_from_first_sheet(path: Path) -> list[list[str | None]]:
    """Read all populated rows from the first worksheet in an XLSX file."""
    with zipfile.ZipFile(path) as workbook_zip:
        shared_strings = read_shared_strings(workbook_zip)

        workbook = ET.fromstring(workbook_zip.read("xl/workbook.xml"))
        relationships = ET.fromstring(workbook_zip.read("xl/_rels/workbook.xml.rels"))
        relationship_targets = {
            relationship.attrib["Id"]: relationship.attrib["Target"]
            for relationship in relationships
        }

        first_sheet = workbook.find("a:sheets/a:sheet", XML_NS)
        if first_sheet is None:
            return []

        relationship_id = first_sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        sheet_path = resolve_xlsx_target(relationship_targets[relationship_id])
        sheet = ET.fromstring(workbook_zip.read(sheet_path))

        rows = []
        for row in sheet.findall("a:sheetData/a:row", XML_NS):
            cells = []
            max_column = -1

            for cell in row.findall("a:c", XML_NS):
                index = column_index(cell.attrib["r"])
                max_column = max(max_column, index)
                cells.append((index, parse_cell_value(cell, shared_strings)))

            values: list[str | None] = [None] * (max_column + 1)
            for index, value in cells:
                values[index] = value
            rows.append(values)

        return rows


def parse_amount(value: str | None) -> float:
    """Parse numeric TACO values for storage in Food_Nutrient.amount."""
    if value is None:
        return 0.0

    normalized_value = value.strip()
    if normalized_value in {"", "Não informado"}:
        return 0.0
    if normalized_value == "Tr":
        return 0.0

    return float(normalized_value.replace(",", "."))


def load_taco_foods(path: Path) -> list[dict[str, object]]:
    """Load food rows from the TACO spreadsheet."""
    rows = read_rows_from_first_sheet(path)
    header = next(row for row in rows if row and row[0] == "Categoria")
    data_rows = rows[rows.index(header) + 1 :]

    foods = []
    for row in data_rows:
        if len(row) < 2 or not row[0] or not row[1]:
            continue

        nutrients = {}
        for index, column_name in enumerate(header):
            nutrient_name = NUTRIENT_COLUMNS.get(column_name or "")
            if nutrient_name is None:
                continue
            nutrients[nutrient_name] = parse_amount(row[index] if index < len(row) else None)

        foods.append(
            {
                "category": row[0],
                "name": row[1],
                "nutrients": nutrients,
            }
        )

    return foods


def populate_foods() -> None:
    """Create or update foods and nutrient amounts from the TACO spreadsheet."""
    initialize_database()
    foods = load_taco_foods(SPREADSHEET_PATH)

    db = SESSEON_LOCAL()
    try:
        vitamin_d = db.query(Nutrient).filter(Nutrient.name == "Vitamina D").first()
        if vitamin_d is not None:
            db.delete(vitamin_d)
            db.flush()

        categories = {
            category.name: category
            for category in db.query(Category).all()
        }
        nutrients = {
            nutrient.name: nutrient
            for nutrient in db.query(Nutrient).all()
        }

        for food_data in foods:
            category = categories[food_data["category"]]
            food = db.query(Food).filter(Food.name == food_data["name"]).first()

            if food is None:
                food = Food(
                    name=food_data["name"],
                    category_id=category.id,
                    brand_id=None,
                )
                db.add(food)
                db.flush()
            else:
                food.category_id = category.id
                food.brand_id = None

            for nutrient_name, amount in food_data["nutrients"].items():
                nutrient = nutrients[nutrient_name]
                association = (
                    db.query(FoodNutrientAssociation)
                    .filter(
                        FoodNutrientAssociation.food_id == food.id,
                        FoodNutrientAssociation.nutrient_id == nutrient.id,
                    )
                    .first()
                )

                if association is None:
                    association = FoodNutrientAssociation(
                        food_id=food.id,
                        nutrient_id=nutrient.id,
                        amount=amount,
                    )
                    db.add(association)
                else:
                    association.amount = amount

        db.commit()
        print(f"{len(foods)} alimentos populados com sucesso.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    populate_foods()
