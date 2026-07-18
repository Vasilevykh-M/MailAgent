"""Версионируемый справочник направлений и контракт классификации писем."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

EmailClassCode = Literal[
    "3D_PRINTERS",
    "CHEMISTRY",
    "FOUNDRY",
    "MOLD_PRINTING",
    "ROBOTIC_CELLS",
    "PRODUCTION_LINES",
    "MACHINES",
    "TECHNICAL_VISION",
    "OTHER_EQUIPMENT",
]
ClassificationStatus = Literal["classified", "new_project", "manual_review"]

NEW_PROJECT_MESSAGE = "Это новый проект"
MANUAL_REVIEW_MESSAGE = "Классификация не выполнена; требуется ручная проверка."
MANUAL_REVIEW_REASON = "Для надёжной классификации недостаточно доступных данных из-за ошибки обработки."


@dataclass(frozen=True)
class EmailClassDefinition:
    code: EmailClassCode
    name_ru: str
    description_ru: str


CLASSIFIER_DEFINITIONS: tuple[EmailClassDefinition, ...] = (
    EmailClassDefinition(
        code="3D_PRINTERS",
        name_ru="3D-принтеры",
        description_ru=(
            "Подбор, покупка, поставка, настройка, ремонт или модернизация промышленных 3D-принтеров, "
            "их компонентов, систем управления и постобработки; основной объект — сам принтер или его оборудование."
        ),
    ),
    EmailClassDefinition(
        code="CHEMISTRY",
        name_ru="Химия для 3D-печати",
        description_ru=(
            "Фотополимерные смолы, связующие, отвердители, катализаторы, промывочные составы и другие "
            "материалы для 3D-печати, когда основной предмет — материал, его свойства, тестирование, поставка "
            "или разработка состава."
        ),
    ),
    EmailClassDefinition(
        code="FOUNDRY",
        name_ru="Литьё и литейное производство",
        description_ru=(
            "Организация, модернизация или автоматизация литейного производства: формовка, заливка металла, "
            "выбивка, очистка отливок, литейная оснастка и оборудование литейного участка."
        ),
    ),
    EmailClassDefinition(
        code="MOLD_PRINTING",
        name_ru="Печать литейных форм",
        description_ru=(
            "Услуга по изготовлению на 3D-принтере готовой литейной формы, стержня, мастер-модели или иной "
            "технологической оснастки; заказчик получает напечатанное изделие, а не принтер."
        ),
    ),
    EmailClassDefinition(
        code="ROBOTIC_CELLS",
        name_ru="Робототехнические комплексы (РТК)",
        description_ru=(
            "Разработка, поставка или модернизация системы на базе промышленного робота или манипулятора, "
            "выполняющего одну операцию: сварку, окраску, загрузку станка, паллетирование, сортировку, "
            "перемещение изделий или контроль качества."
        ),
    ),
    EmailClassDefinition(
        code="PRODUCTION_LINES",
        name_ru="Производственные линии",
        description_ru=(
            "Комплексная автоматизированная или роботизированная линия как единая система из нескольких единиц "
            "оборудования и последовательных операций производства, сборки, обработки, контроля, упаковки, "
            "сортировки или транспортировки."
        ),
    ),
    EmailClassDefinition(
        code="MACHINES",
        name_ru="Станки",
        description_ru=(
            "Отдельный металлообрабатывающий, деревообрабатывающий или специальный промышленный станок: "
            "токарный, фрезерный, шлифовальный, сверлильный, режущий, обрабатывающий центр, а также его "
            "оснастка, автоматизация или модернизация."
        ),
    ),
    EmailClassDefinition(
        code="TECHNICAL_VISION",
        name_ru="Техническое зрение",
        description_ru=(
            "Системы автоматического визуального контроля, поиска дефектов, измерения геометрии, распознавания, "
            "позиционирования или сортировки: камеры, освещение, оптика, 2D/3D-сканеры, алгоритмы и ПО "
            "обработки изображений."
        ),
    ),
    EmailClassDefinition(
        code="OTHER_EQUIPMENT",
        name_ru="Прочее промышленное оборудование",
        description_ru=(
            "Явно промышленное оборудование или запчасти вне специальных классов: компрессоры, печи, насосы, "
            "конвейеры и вспомогательное оборудование. Это не универсальный запасной вариант для неясного письма."
        ),
    ),
)

CLASS_NAME_RU_BY_CODE: dict[EmailClassCode, str] = {item.code: item.name_ru for item in CLASSIFIER_DEFINITIONS}


class EmailClassification(BaseModel):
    """Строгий результат определения единственного направления письма."""

    model_config = ConfigDict(extra="forbid")

    status: ClassificationStatus
    class_code: EmailClassCode | None
    class_name_ru: str | None
    reason_ru: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    message_ru: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_consistency(self) -> EmailClassification:
        if not self.reason_ru.strip() or not self.message_ru.strip():
            raise ValueError("reason_ru и message_ru не могут быть пустыми.")
        if self.status == "classified":
            if self.class_code is None or self.class_name_ru is None or not self.class_name_ru.strip():
                raise ValueError("Для статуса classified обязательны class_code и class_name_ru.")
            if self.class_name_ru != CLASS_NAME_RU_BY_CODE[self.class_code]:
                raise ValueError("class_name_ru не соответствует class_code.")
        elif self.status == "new_project":
            if self.class_code is not None or self.class_name_ru is not None:
                raise ValueError("Для статуса new_project class_code и class_name_ru должны быть null.")
            if self.message_ru != NEW_PROJECT_MESSAGE:
                raise ValueError("Для статуса new_project message_ru должен быть точной фразой нового проекта.")
        elif self.class_code is not None or self.class_name_ru is not None:
            raise ValueError("Для статуса manual_review class_code и class_name_ru должны быть null.")
        return self


def manual_review_classification(reason_ru: str = MANUAL_REVIEW_REASON) -> EmailClassification:
    """Возвращает безопасный результат при сбое либо недостатке надёжных данных."""

    return EmailClassification(
        status="manual_review",
        class_code=None,
        class_name_ru=None,
        reason_ru=reason_ru,
        confidence=0,
        message_ru=MANUAL_REVIEW_MESSAGE,
    )


def classifier_prompt_section() -> str:
    """Формирует единственный системный раздел с правилами классификации."""

    class_list = "\n".join(
        f"- `{item.code}` — {item.name_ru}: {item.description_ru}" for item in CLASSIFIER_DEFINITIONS
    )
    return f"""Email project-classification rules:
Use every supplied item of evidence: subject, normalized body, each level of the forwarded-chain digest, attachment text or final attachment summaries, and warnings about unavailable or unrecognized attachments. Determine the primary business object and expected customer deliverable semantically. Do not classify by isolated keywords, attachment filenames, sender identity, organization name, or generic words such as \"equipment\", \"automation\" or \"project\".

Allowed classes (select exactly one only when a class genuinely applies):
{class_list}

Resolve overlap by the primary requested deliverable and prefer the more specialized class:
1. A service to manufacture a printed foundry mold, core, master model or tooling item is `MOLD_PRINTING`.
2. Purchase, supply, repair or setup of a printer itself is `3D_PRINTERS`.
3. Resin, binder, hardener or another material for 3D printing is `CHEMISTRY`.
4. One operation centered on an industrial robot is `ROBOTIC_CELLS`.
5. Several connected operations and equipment supplied as one system is `PRODUCTION_LINES`.
6. One industrial machine is `MACHINES`.
7. Cameras, scanners, image processing or visual inspection as the primary task is `TECHNICAL_VISION`, even inside a robot cell, line or machine.
8. Foundry technology or equipment in a foundry area is `FOUNDRY`.
9. Use `OTHER_EQUIPMENT` only for clearly industrial equipment or spare parts outside the specialized classes; never use it as a fallback for an unclear or unrelated email.

If no business area above semantically applies, return `status: new_project`, null class fields, and the exact `message_ru`: `{NEW_PROJECT_MESSAGE}`. Use `new_project` for administrative, marketing, personal, irrelevant or fundamentally different requests. Do not infer a new project from a processing failure, unavailable attachment, missing reliable evidence, or an invalid model response: in those cases return `status: manual_review`, null class fields, confidence 0, and a concise Russian reason. For a genuine ambiguity, select the most likely one class, explain uncertainty in `reason_ru`, and add a warning in `warnings_ru` when that field is available."""
