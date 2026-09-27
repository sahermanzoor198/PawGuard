import streamlit as st
from groq import Groq

# --------------------------
# PAGE CONFIG
# --------------------------

st.set_page_config(
    page_title="PawGuard AI",
    page_icon="🐾",
    layout="wide"
)

# --------------------------
# HEADER
# --------------------------

st.title("🐾 PawGuard AI")
st.caption("AI-Powered Pet Emergency Triage Assistant")

st.warning(
    "This tool provides general pet-health guidance only and is not a substitute for professional veterinary care."
)

# --------------------------
# GROQ CLIENT
# --------------------------

try:
    client = Groq(
        api_key=st.secrets["GROQ_API_KEY"]
    )
except Exception:
    st.error(
        "Groq API key not found. Please add GROQ_API_KEY in Streamlit Secrets."
    )
    st.stop()

# --------------------------
# PET PROFILE
# --------------------------

st.header("🐶 Pet Profile")

col1, col2 = st.columns(2)

with col1:
    pet_name = st.text_input("Pet Name")

    pet_type = st.selectbox(
        "Pet Type",
        [
            "Dog",
            "Cat",
            "Bird",
            "Rabbit",
            "Other"
        ]
    )

with col2:
    pet_age = st.number_input(
        "Age (Years)",
        min_value=0,
        max_value=50,
        value=1
    )

    pet_weight = st.number_input(
        "Weight (kg)",
        min_value=0.0,
        value=1.0
    )

# --------------------------
# EMERGENCY CHECKLIST
# --------------------------

st.header("🚨 Emergency Symptoms")

emergency_symptoms = st.multiselect(
    "Select all symptoms that apply",
    [
        "Difficulty Breathing",
        "Bleeding",
        "Seizure",
        "Collapse",
        "Poison Exposure",
        "Vomiting",
        "Not Eating",
        "Low Energy",
        "Diarrhea",
        "Coughing",
        "Fever",
        "Limping"
    ]
)

# --------------------------
# DETAILS
# --------------------------

st.header("📝 Symptom Details")

symptoms = st.text_area(
    "Describe what is happening",
    placeholder="Example: My dog has been vomiting since yesterday and refuses to eat."
)

# --------------------------
# ANALYZE BUTTON
# --------------------------

if st.button("🔍 Analyze Symptoms"):

    if symptoms.strip() == "":
        st.warning("Please describe the symptoms.")
        st.stop()

    prompt = f"""
You are PawGuard AI.

You help pet owners understand potential urgency levels.

Pet Information:

Name: {pet_name}
Type: {pet_type}
Age: {pet_age}
Weight: {pet_weight} kg

Emergency Symptoms:
{", ".join(emergency_symptoms)}

Detailed Symptoms:
{symptoms}

IMPORTANT:

Do not claim to diagnose diseases.

Provide output in exactly this format:

🚨 Risk Level:
Low / Medium / High

🔍 Possible Causes:
- Cause 1
- Cause 2
- Cause 3

🏠 Immediate Actions:
- Action 1
- Action 2
- Action 3

👨‍⚕️ Vet Recommendation:
Short recommendation

⚠️ Emergency Warning:
Short warning if urgent
"""

    try:

        with st.spinner("Analyzing symptoms..."):

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful pet emergency triage assistant."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0.3
            )

        result = response.choices[0].message.content

        st.success("Analysis Complete")

        st.markdown(result)

    except Exception as e:

        st.error(
            "An error occurred while contacting the AI model."
        )

        st.code(str(e))
