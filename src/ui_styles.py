from __future__ import annotations

import streamlit as st


class UiStyles:
    """Zentrale CSS-Styles der Streamlit-Anwendung."""

    @staticmethod
    def apply() -> None:
        st.html(
            """
            <style>
            /* ---------------------------------------------------------
               Formblatt 1 herunterladen – Grün
               --------------------------------------------------------- */

            .st-key-download_formblatt1 button {
                background-color: #198754 !important;
                border-color: #198754 !important;
                color: #ffffff !important;
                font-weight: 600 !important;
                border-radius: 10px !important;
                transition:
                    background-color 0.2s ease,
                    border-color 0.2s ease,
                    transform 0.1s ease !important;
            }

            .st-key-download_formblatt1 button:hover {
                background-color: #157347 !important;
                border-color: #146c43 !important;
                color: #ffffff !important;
            }

            .st-key-download_formblatt1 button:active {
                background-color: #0f5132 !important;
                border-color: #0f5132 !important;
                transform: translateY(1px);
            }

            .st-key-download_formblatt1 button:focus {
                box-shadow:
                    0 0 0 0.2rem rgba(25, 135, 84, 0.25)
                    !important;
            }

            /* Text und Symbol innerhalb des Download-Buttons */
            .st-key-download_formblatt1 button p,
            .st-key-download_formblatt1 button span,
            .st-key-download_formblatt1 button svg {
                color: #ffffff !important;
                fill: #ffffff !important;
            }


            /* ---------------------------------------------------------
               Antrag senden – Blau
               --------------------------------------------------------- */

            .st-key-submit_application_prototype button {
                background-color: #0d6efd !important;
                border-color: #0d6efd !important;
                color: #ffffff !important;
                font-weight: 600 !important;
                border-radius: 10px !important;
                transition:
                    background-color 0.2s ease,
                    border-color 0.2s ease,
                    transform 0.1s ease !important;
            }

            .st-key-submit_application_prototype button:hover {
                background-color: #0b5ed7 !important;
                border-color: #0a58ca !important;
                color: #ffffff !important;
            }

            .st-key-submit_application_prototype button:active {
                background-color: #084298 !important;
                border-color: #084298 !important;
                transform: translateY(1px);
            }

            .st-key-submit_application_prototype button:focus {
                box-shadow:
                    0 0 0 0.2rem rgba(13, 110, 253, 0.25)
                    !important;
            }

            /* Text und Symbol innerhalb des Senden-Buttons */
            .st-key-submit_application_prototype button p,
            .st-key-submit_application_prototype button span,
            .st-key-submit_application_prototype button svg {
                color: #ffffff !important;
                fill: #ffffff !important;
            }
            </style>
            """
        )