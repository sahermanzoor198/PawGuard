import streamlit as st
from groq import Groq

st.set_page_config(
    page_title="PawGuard AI",
    page_icon="🐾",
    layout="wide"
)

st.title("🐾 PawGuard AI")
st.subheader("AI Pet Emergency Triage Assistant")

st.info(
    "PawGuard AI provides general pet-health guidance only. "
    "It is not a substitute for a licensed veterinarian."
)

# Groq Client
client = Groq(api_key=st.secrets["GROQ_API_KEY"])

# Pet Information
st.header("Pet Profile")

pet_name = st.text_input("Pet Name")

pet_type = st.selectbox(
    "Pet Type",
    ["Dog", "Cat", "Bird", "Rabbit", "Other"]
)

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

# Symptoms
st.header("Symptoms")

symptoms = st.text_area(
    "Describe Symptoms",
    placeholder="Example: Vomiting, not eating, low energy"
)

if st.button("Analyze Symptoms"):

    if symptoms.strip() == "":
        st.warning("Please enter symptoms.")
    else:

        prompt = f"""
You are PawGuard AI, a pet emergency triage assistant.

Pet Name: {pet_name}
Pet Type: {pet_type}
Age: {pet_age}
Weight: {pet_weight} kg

Symptoms:
{symptoms}

Respond using exactly this format:

🚨 Risk Level:
(Low / Medium / High)

🔍 Possible Causes:
- Cause 1
- Cause 2
- Cause 3

🏠 Immediate Actions:
- Action 1
- Action 2
- Action 3

👨‍⚕️ Vet Recommendation:
Explain whether a vet visit is recommended.

Keep the answer simple and easy to understand.
"""

        with st.spinner("Analyzing symptoms..."):

            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful pet health assistant."
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
