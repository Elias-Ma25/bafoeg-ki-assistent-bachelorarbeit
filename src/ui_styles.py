from __future__ import annotations

import streamlit as st


class UiStyles:
    """Zentrale CSS-Styles der Streamlit-Anwendung."""

    @staticmethod
    def apply() -> None:
        st.html(
            """
            <style>
            
            /*  =========================================================
                Einführungsbereich
                ========================================================= */

            .st-key-welcome_intro_card {
                background:
                    linear-gradient(
                        135deg,
                        #f8fbff 0%,
                        #eef7ff 100%
                    );  

                border: 1px solid #bfdbfe;
                border-radius: 18px;

                padding: 1rem 1.2rem 1.2rem;
                margin: 0.75rem 0 1.25rem;
            
                box-shadow:
                    0 6px 20px rgba(30, 64, 175, 0.08);
            }
            
            .st-key-welcome_intro_card h3 {
                color: #1e3a5f;
                margin-top: 0;
                margin-bottom: 0.4rem;
            }
            
            
            /* Karten der beiden Nutzungsmodi */
            
            .st-key-welcome_consultation_card,
            .st-key-welcome_application_card {
                background: #ffffff;
            
                border: 1px solid #dbeafe;
                border-radius: 14px;
            
                padding: 0.8rem 1rem;
                min-height: 180px;
            
                box-shadow:
                    0 2px 10px rgba(15, 23, 42, 0.05);
            }
            
            .st-key-welcome_consultation_card h4,
            .st-key-welcome_application_card h4 {
                color: #0f4c81;
                margin-top: 0;
            }
            
            
            /* Schließen-Schaltfläche */
            
            .st-key-welcome_intro_close button {
                min-width: 2.1rem !important;
                width: 2.1rem !important;
                height: 2.1rem !important;
            
                padding: 0 !important;
                border: none !important;
                border-radius: 50% !important;
            
                background: transparent !important;
                color: #64748b !important;
            
                font-size: 1rem !important;
                font-weight: 700 !important;
            }
            
            .st-key-welcome_intro_close button:hover {
                background: #dbeafe !important;
                color: #1e3a5f !important;
            }
            
            
            /* Einführung erneut öffnen */
            
            .st-key-welcome_intro_reopen button {
                background: #eff6ff !important;
                border: 1px solid #93c5fd !important;
                color: #1d4ed8 !important;
            
                font-weight: 600 !important;
                border-radius: 10px !important;
            }
            
            .st-key-welcome_intro_reopen button:hover {
                background: #dbeafe !important;
                border-color: #60a5fa !important;
                color: #1e40af !important;
            }
            
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
