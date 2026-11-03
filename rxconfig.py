import reflex as rx
from reflex_base.plugins.sitemap import SitemapPlugin

# Agregar la importación de Radix
from reflex_components_radix.plugin import RadixThemesPlugin

config = rx.Config(
    app_name="Chatly",
    plugins=[
        SitemapPlugin(),
        RadixThemesPlugin()
    ],
    frontend_packages=["@supabase/supabase-js"],
)