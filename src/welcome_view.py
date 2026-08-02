from __future__ import annotations

import streamlit as st


class WelcomeView:
    """Ein- und ausblendbare Einführung der Anwendung."""

    STATE_KEY = "welcome_intro_visible"

    @classmethod
    def _set_visible(
        cls,
        visible: bool,
    ) -> None:
        st.session_state[cls.STATE_KEY] = visible

    @classmethod
    def render(cls) -> None:
        """Zeigt die Einführung oder die Schaltfläche zum Öffnen."""

        if cls.STATE_KEY not in st.session_state:
            st.session_state[cls.STATE_KEY] = True

        # --------------------------------------------------------
        # Einführung wurde geschlossen
        # --------------------------------------------------------
        if not st.session_state[cls.STATE_KEY]:
            spacer_column, button_column = st.columns(
                [0.76, 0.24]
            )

            with button_column:
                with st.container(
                    key="welcome_intro_reopen",
                ):
                    st.button(
                        "ℹ️ Einführung anzeigen",
                        key="open_welcome_intro",
                        use_container_width=True,
                        on_click=cls._set_visible,
                        args=(True,),
                    )

            return

        # --------------------------------------------------------
        # Einführung ist sichtbar
        # --------------------------------------------------------
        with st.container(
            key="welcome_intro_card",
        ):
            title_column, close_column = st.columns(
                [0.94, 0.06]
            )

            with title_column:
                st.markdown(
                    "### 👋 Willkommen beim KI-gestützten "
                    "BAföG-Assistenten"
                )

            with close_column:
                with st.container(
                    key="welcome_intro_close",
                ):
                    st.button(
                        "✕",
                        key="close_welcome_intro",
                        help="Einführung schließen",
                        use_container_width=True,
                        on_click=cls._set_visible,
                        args=(False,),
                    )

            st.markdown(
                """
                Hier erhältst du Unterstützung bei allgemeinen
                BAföG-Fragen und bei der prototypischen Vorbereitung
                eines BAföG-Erstantrags.

                Du kannst zwischen zwei Nutzungsmodi wählen:
                """
            )

            consultation_column, application_column = st.columns(
                2,
                gap="medium",
            )

            with consultation_column:
                with st.container(
                    key="welcome_consultation_card",
                ):
                    st.markdown(
                        "#### 💬 1. Freie BAföG-Beratung"
                    )

                    st.write(
                        "Stelle z.B. allgemeine Fragen zu BAföG, "
                        "Formblättern, Voraussetzungen oder "
                        "benötigten Nachweisen."
                    )

                    st.write(
                        "Du kannst deine Fragen frei formulieren "
                        "und jederzeit Rückfragen stellen."
                    )

            with application_column:
                with st.container(
                    key="welcome_application_card",
                ):
                    st.markdown(
                        "#### 📄 2. BAföG-Erstantrag vorbereiten"
                    )

                    st.write(
                        "Lade deine dokumente hoch. Der Assistent "
                        "übernimmt erkannte Angaben und fragt nur noch "
                        "fehlende Informationen ab."
                    )

                    st.write(
                        "Anschließend kannst du die Nachweis-Checkliste "
                        "und Formularvorschau kontrollieren, Angaben "
                        "ergänzen und Formblatt 1 herunterladen."
                    )

            st.info(
                "Diese Anwendung ist ein Prototyp im Rahmen einer "
                "Bachelorarbeit. Sie ersetzt keine rechtsverbindliche "
                "Beratung."
            )