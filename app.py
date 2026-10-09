import urllib.parse
import time
import streamlit as st
from google import genai
from google.genai import types
from prompts import SUMMARY_REQUEST_PROMPT, SYSTEM_PROMPT, WELCOME_MESSAGE_TEMPLATE

MODEL_NAME = "gemini-3.8-flash"
st.set_page_config(page_title="MacroSnap", page_icon="??")
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]


@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


gemini_client = get_gemini_client()


def render_message(message):
    with st.chat_message(message["role"]):
        if message["kind"] == "text":
            st.write(message["content"])
        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):
    st.session_state.messages.append({"role": role, "kind": kind, "content": content})
    render_message(st.session_state.messages[-1])


def ask_gemini(parts, retries=5):
    for attempt in range(retries):
        try:
            return st.session_state.chat.send_message(parts).text
        except Exception as error:
            if ("503" in str(error) or "UNAVAILABLE" in str(error)) and attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            return f"Sorry, something went wrong: {error}"


if "onboarded" not in st.session_state:
    st.title("?? MacroSnap")
    st.caption("Snap it. Track it. Get your nutrition summary on WhatsApp.")
    with st.form("onboarding_form"):
        name = st.text_input("Your name")
        whatsapp_number = st.text_input(
            "WhatsApp number (with country code)",
            placeholder="+91XXXXXXXXXX",
            help="Your summary will be formatted for this number.",
        )
        submitted = st.form_submit_button("Let's go ??")
    if submitted:
        if not name.strip() or not whatsapp_number.strip():
            st.warning("Please fill in both your name and WhatsApp number.")
        else:
            clean_num = whatsapp_number.strip().replace("+", "").replace(" ", "").replace("-", "")
            st.session_state.name = name.strip()
            st.session_state.whatsapp_number = clean_num
            st.session_state.chat = gemini_client.chats.create(
                model=MODEL_NAME,
                config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
            )
            st.session_state.messages = []
            st.session_state.onboarded = True
            st.rerun()
    st.stop()

header_col, button_col = st.columns([5, 3], vertical_alignment="center")
with header_col:
    st.title("?? MacroSnap")
with button_col:
    send_disabled = len(st.session_state.messages) <= 1
    if st.button("?? Generate WhatsApp Summary", disabled=send_disabled, use_container_width=True):
        with st.spinner("Summarizing your day..."):
            summary = ask_gemini([SUMMARY_REQUEST_PROMPT])
            encoded_summary = urllib.parse.quote(f"Hi {st.session_state.name}!\n\nHere is your MacroSnap Diet Summary:\n\n{summary}")
            wa_link = f"https://wa.me/{st.session_state.whatsapp_number}?text={encoded_summary}"
            st.session_state.wa_link = wa_link
            st.session_state.summary_text = summary

if "wa_link" in st.session_state:
    st.success("? Summary Generated!")
    st.link_button("?? Click here to Open in WhatsApp", st.session_state.wa_link, use_container_width=True)
    with st.expander("Preview Summary"):
        st.write(st.session_state.summary_text)

st.caption(f"Logged in as **{st.session_state.name}** | Target WhatsApp: **+{st.session_state.whatsapp_number}**")
if not st.session_state.messages:
    add_message("assistant", "text", WELCOME_MESSAGE_TEMPLATE.format(name=st.session_state.name))
else:
    for message in st.session_state.messages:
        render_message(message)

user_input = st.chat_input(
    "Ask a nutrition question, or attach a photo of your meal",
    accept_file=True,
    file_type=["jpg", "jpeg", "png"],
)
if user_input:
    photo = user_input.files[0] if user_input.files else None
    text = user_input.text
    parts = []
    if photo is not None:
        photo_bytes = photo.getvalue()
        add_message("user", "image", photo_bytes)
        parts.append(types.Part.from_bytes(data=photo_bytes, mime_type=photo.type))
    if text:
        add_message("user", "text", text)
        parts.append(text)
    elif photo is not None:
        parts.append("What is this meal? Give me the estimated calories and macros (protein, carbs, fat).")
    with st.spinner("Analyzing nutrition..."):
        answer = ask_gemini(parts)
    add_message("assistant", "text", answer)
