import streamlit as st
st.title("Safe to Swim")
st.write("Is it safe to swim today?")
lake= st.selectbox("Select your lake", ["Select from dropdown menu", "Sammamish Lake", "Pine Lake"])
check=st.button("Check out your lake")
if check:
    st.write(lake)