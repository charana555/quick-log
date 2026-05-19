import streamlit as st
from utils.styles import inject_styles

log_uploader = st.Page(
    "pages/log_uploader.py", title="Log Uploader", icon=":material/upload:", default=True
)

configuration_settings = st.Page(
    "pages/settings.py", title="Configuration Settings", icon=":material/settings:"
)

nav_dict = {
    "Quick Log": [log_uploader],
    "Settings": [configuration_settings]
}

def main():
    st.set_page_config(layout='wide', page_title="Quick Log")
    inject_styles()
    pg = st.navigation(nav_dict)
    pg.run()

if __name__ == "__main__":
    main()
