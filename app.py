
import streamlit as st

st.set_page_config(
    page_title='PawGuard AI',
    page_icon='🐾',
    layout='wide'
)

st.title('🐾 PawGuard AI')
st.subheader('Pet Emergency Triage Assistant')

pet_name = st.text_input('Pet Name')
pet_type = st.selectbox('Pet Type', ['Dog', 'Cat', 'Bird', 'Rabbit', 'Other'])
age = st.number_input('Age (years)', min_value=0, value=1)
weight = st.number_input('Weight (kg)', min_value=0.0, value=1.0)

symptoms = st.text_area(
    'Describe Symptoms',
    placeholder='Example: Vomiting, not eating, low energy'
)

if st.button('Analyze'):
    if symptoms.strip():
        st.success('PawGuard AI analysis feature will be connected to Groq in the next step.')
        st.write('Pet:', pet_name)
        st.write('Type:', pet_type)
        st.write('Age:', age)
        st.write('Weight:', weight, 'kg')
        st.write('Symptoms:', symptoms)
    else:
        st.warning('Please enter symptoms.')
