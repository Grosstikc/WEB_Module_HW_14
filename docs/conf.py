# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'my_fastapi_project'
copyright = '2024, Ross'
author = 'Ross'
release = '1.0'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = []

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']



# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

html_theme = 'alabaster'
html_static_path = ['_static']

import os
import sys
sys.path.insert(0, os.path.abspath('D:\IT_courses\Python\projects\WEB_HW_11(REST_API_ON_FAST_API)\my_fastapi_project\app')) 

extensions = [
    'sphinx.ext.autodoc',  # Додає підтримку автоматичного документування
    'sphinx.ext.coverage',  # Перевіряє покриття документацією
    'sphinx.ext.napoleon',  # Підтримка Google та NumPy стилів docstrings
]

html_theme = 'sphinx_rtd_theme'
