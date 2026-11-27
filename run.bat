@echo off
cd /d "C:\Projects\IntelliCampus_AI"
python -m pip install streamlit
python -m streamlit run app.py --server.port 8501
pause