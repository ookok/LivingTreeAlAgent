```mermaid
graph TD
    livingtree_desktop_shell --> livingtree_main
    livingtree_main --> livingtree___init__
    livingtree___init__ --> livingtree___main__
    livingtree___main__ --> livingtree_api_audit
    livingtree_api_audit --> livingtree_api_auth
    livingtree_api_auth --> livingtree_api_code_api
    livingtree_api_code_api --> livingtree_api_cognition_stream
    livingtree_api_cognition_stream --> livingtree_api_doc_routes
    livingtree_api_doc_routes --> livingtree_api_github_auth
    livingtree_api_github_auth --> livingtree_api_htmx_business
    livingtree_api_htmx_business --> livingtree_api_htmx_living
    livingtree_api_htmx_living --> livingtree_api_htmx_web
    livingtree_api_htmx_web --> livingtree_api_openai_proxy
    livingtree_api_openai_proxy --> livingtree_api_request_buffer
```