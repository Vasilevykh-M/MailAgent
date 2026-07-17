from __future__ import annotations

from mail_agent.messages.forwarded import extract_forwarded_chain, extract_forwarded_message, format_forwarded_chain


def test_extracts_russian_forwarded_message_headers_and_body() -> None:
    value = """Коллеги, прошу посмотреть.

---------- Пересланное сообщение ----------
От: АО КМЗ <sales@example.test>
Дата: 09.07.2026 10:30
Кому: Коммерческий отдел <team@example.test>
Тема: Вх письмо 613 от 09.07.2026 АО КМЗ Запрос ТКП

Добрый день.
Просим направить ТКП.
"""

    forwarded = extract_forwarded_message(value)

    assert forwarded is not None
    assert forwarded.sender == "АО КМЗ <sales@example.test>"
    assert forwarded.date == "09.07.2026 10:30"
    assert forwarded.subject == "Вх письмо 613 от 09.07.2026 АО КМЗ Запрос ТКП"
    assert forwarded.recipients == "Коммерческий отдел <team@example.test>"
    assert forwarded.forwarder_note == "Коллеги, прошу посмотреть."
    assert forwarded.body == "Добрый день.\nПросим направить ТКП."


def test_does_not_treat_plain_text_as_forwarded_message() -> None:
    assert extract_forwarded_message("Текст про forwarded message без блока заголовков.") is None


def test_extracts_all_yandex_forwarding_levels_and_removes_disclaimer() -> None:
    value = """Нужно взять в работу.

-------- Пересылаемое сообщение --------
06.05.2026, 10:31, Алексей Падучев (alexey@example.test):
Кому: Мария Викторовна (maria@example.test)
Тема: Вх письмо 440 Запрос по роботизации

Срочно созвонитесь с заказчиком и согласуйте техническое решение.

-------- Пересылаемое сообщение --------
05.05.2026, 16:07, Екатерина Сычикова (info@example.test):
Кому: Коммерческий отдел (sales@example.test)
Тема: Запрос по роботизации

Просим направить ТКП по роботизации процессов.
This email is intended solely for business correspondence. If you are not the intended recipient, notify the sender.
"""

    chain = extract_forwarded_chain(value)

    assert chain is not None
    assert chain.outer_note == "Нужно взять в работу."
    assert len(chain.messages) == 2
    assert chain.messages[0].sender == "Алексей Падучев (alexey@example.test)"
    assert chain.messages[0].subject == "Вх письмо 440 Запрос по роботизации"
    assert chain.messages[0].body == "Срочно созвонитесь с заказчиком и согласуйте техническое решение."
    assert chain.messages[1].sender == "Екатерина Сычикова (info@example.test)"
    assert chain.messages[1].body == "Просим направить ТКП по роботизации процессов."
    formatted = format_forwarded_chain(chain)
    assert "[Пересланное сообщение 1]" in formatted
    assert "[Пересланное сообщение 2]" in formatted
    assert "intended solely" not in formatted
