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
               Frage erklären – Magenta, ohne Schatten
               --------------------------------------------------------- */
            
            .st-key-hybrid_help_button {
                display: flex;
                justify-content: flex-end;
                align-items: center;
            }
            
            .st-key-hybrid_help_button button {
                width: 100% !important;
                min-height: 2.65rem !important;
                padding: 0.55rem 1rem !important;
            
                display: inline-flex !important;
                align-items: center !important;
                justify-content: center !important;
                gap: 0.4rem !important;
            
                background:
                    linear-gradient(
                        135deg,
                        #d81b60 0%,
                        #ad1457 100%
                    ) !important;
            
                border: 1px solid #ad1457 !important;
                border-radius: 10px !important;
            
                color: #ffffff !important;
                font-size: 0.9rem !important;
                font-weight: 650 !important;
                line-height: 1.2 !important;
            
                box-shadow: none !important;
            
                transition:
                    background 0.16s ease,
                    border-color 0.16s ease
                    !important;
            }
            
            .st-key-hybrid_help_button button:hover {
                background:
                    linear-gradient(
                        135deg,
                        #c2185b 0%,
                        #880e4f 100%
                    ) !important;
            
                border-color: #880e4f !important;
                color: #ffffff !important;
            
                transform: none !important;
                box-shadow: none !important;
            }
            
            .st-key-hybrid_help_button button:active {
                background: #880e4f !important;
                border-color: #880e4f !important;
            
                transform: none !important;
                box-shadow: none !important;
            }
            
            .st-key-hybrid_help_button button:focus {
                outline:
                    3px solid rgba(236, 72, 153, 0.22)
                    !important;
            
                outline-offset: 2px !important;
                box-shadow: none !important;
            }
            
            .st-key-hybrid_help_button button p,
            .st-key-hybrid_help_button button span,
            .st-key-hybrid_help_button button svg {
                margin: 0 !important;
            
                color: #ffffff !important;
                fill: #ffffff !important;
            
                font-size: 0.9rem !important;
                font-weight: 650 !important;
                line-height: 1.2 !important;
                white-space: nowrap !important;
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

        st.markdown(
            """
            <style>
            /* Nachricht senden: weiß mit grünem Rahmen */
            .st-key-send_chat_message_button button {
                background-color: #ffffff !important;
                border: 2px solid #22c55e !important;
                color: #15803d !important;
                font-weight: 600 !important;
                border-radius: 9px !important;
                box-shadow: none !important;
            }
        
            .st-key-send_chat_message_button button:hover {
                background-color: #f0fdf4 !important;
                border-color: #16a34a !important;
                color: #166534 !important;
                box-shadow: none !important;
            }
        
            .st-key-send_chat_message_button button:active {
                background-color: #dcfce7 !important;
                border-color: #15803d !important;
                color: #14532d !important;
            }
            
            /* Chat und Antrag löschen: weiß mit rotem Rahmen */
            .st-key-clear_chat_application_button button {
                background-color: #ffffff !important;
                border: 2px solid #ef4444 !important;
                color: #dc2626 !important;
                font-weight: 600 !important;
                border-radius: 9px !important;
                box-shadow: none !important;
            }
            
            .st-key-clear_chat_application_button button:hover {
                background-color: #fef2f2 !important;
                border-color: #dc2626 !important;
                color: #b91c1c !important;
                box-shadow: none !important;
            }
            
            .st-key-clear_chat_application_button button:active {
                background-color: #fee2e2 !important;
                border-color: #b91c1c !important;
                color: #991b1b !important;
            }
            
            .st-key-clear_chat_application_button button:focus-visible {
                outline: 3px solid rgba(239, 68, 68, 0.22) !important;
                outline-offset: 2px !important;
            }
            
            /* Abstände innerhalb des Chatbereichs reduzieren */
            .st-key-chat_area [data-testid="stVerticalBlock"] {
                gap: 0.55rem !important;
            }
            
            /* Sichtbarer innerer Bereich des Nachrichteneingabefeldes */
            .st-key-chat_message_input
            [data-testid="stTextArea"]
            div:has(> textarea) {
                background-color: #ffffff !important;
                border: 1px solid #888888 !important;
                border-radius: 10px !important;
                box-shadow: none !important;
            }
        
            /* Zustand beim Anklicken */
            .st-key-chat_message_input
            [data-testid="stTextArea"]
            div:has(> textarea:focus) {
                border-color: #dc2627 !important;
                box-shadow: 0 0 0 0px #999999 !important;
            }
        
            /* Textarea selbst ohne eigenen zweiten Rahmen */
            .st-key-chat_message_input
            [data-testid="stTextArea"]
            textarea {
                background-color: transparent !important;
                border: none !important;
                outline: none !important;
                box-shadow: none !important;
            }
            /* Einführung bestätigen und ausblenden */
            .st-key-welcome_understood_button button {
                background-color: #14b8a6 !important;
                border: 2px solid #14b8a6 !important;
                color: #ffffff !important;
                font-weight: 700 !important;
                border-radius: 10px !important;
                box-shadow: none !important;
            }
        
            .st-key-welcome_understood_button button:hover {
                background-color: #0d9488 !important;
                border-color: #0d9488 !important;
                color: #ffffff !important;
            }
        
            .st-key-welcome_understood_button button:active {
                background-color: #0f766e !important;
                border-color: #0f766e !important;
                color: #ffffff !important;
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
