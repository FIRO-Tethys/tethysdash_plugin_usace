from intake.source import base

class CustomExample(base.DataSource):
    container = "python"
    version = "0.0.1"
    name = "custom_example"
    visualization_args = {}
    visualization_group = "Example"
    visualization_label = "Custom Example"
    visualization_type = "custom"

    def __init__(self, metadata=None):
        super(CustomExample, self).__init__(metadata=metadata)

    def read(self):
        """
            Return the configuration for the custom component
        """
        mfe_unpkg_url = "http://localhost:3000/remoteEntry.js"
        # mfe_unpkg_url = "https://unpkg.com/mfe-ol@latest/dist/remoteEntry.js"
        mfe_scope = "custom_component_scope"
        mfe_module = "./CustomComponent"

        return {
            "url": mfe_unpkg_url,
            "scope": mfe_scope,
            "module": mfe_module,
        }