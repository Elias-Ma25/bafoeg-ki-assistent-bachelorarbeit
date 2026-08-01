from __future__ import annotations

import streamlit as st


def categorize_checklist(
    checklist: dict,
) -> tuple[dict, dict, dict]:
    available_items: dict = {}
    required_open_items: dict = {}
    optional_items: dict = {}

    hidden_statuses = {
        "nicht_erforderlich",
        "nicht_im_fokus",
    }

    optional_statuses = {
        "optional",
        "zu_pruefen",
    }

    available_statuses = {
        "vorhanden",
        "zielformular",
    }

    for item_key, item in checklist.items():
        status = str(
            item.get("status", "")
        ).strip().lower()

        required = item.get("required") is True
        uploaded = item.get("uploaded") is True

        if uploaded or status in available_statuses:
            available_items[item_key] = item
            continue

        if required and status not in hidden_statuses:
            required_open_items[item_key] = item
            continue

        if status in optional_statuses:
            optional_items[item_key] = item

    return (
        available_items,
        required_open_items,
        optional_items,
    )


def render_checklist_items(
    items: dict,
    icon: str,
    empty_message: str,
) -> None:
    if not items:
        st.caption(empty_message)
        return

    item_list = list(items.values())

    for index, item in enumerate(item_list):
        label = str(
            item.get("label", "")
        ).strip()

        reason = str(
            item.get("reason", "")
        ).strip()

        st.markdown(f"{icon} **{label}**")

        if reason:
            st.caption(reason)

        if index < len(item_list) - 1:
            st.divider()