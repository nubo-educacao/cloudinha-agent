import json
import httpx
from typing import Any, Dict
from src.lib.error_handler import safe_execution

@safe_execution(error_type="tool_error", default_return='{"success": false, "error": "Erro ao consultar CEP."}')
def lookupCEPTool(cep: str) -> str:
    """Consulta informações de endereço (Rua, Bairro, Cidade, Estado) usando o ViaCEP. Return is a JSON string of ViaCEP output."""
    
    # Clean the input CEP
    clean_cep = "".join(filter(str.isdigit, cep))
    
    if len(clean_cep) != 8:
        return json.dumps({"success": False, "error": "CEP inválido. Deve conter 8 dígitos."})
    
    # Try BrasilAPI first (more stable than ViaCEP usually)
    url_brasil_api = f"https://brasilapi.com.br/api/cep/v1/{clean_cep}"
    
    try:
        import requests
        response = requests.get(url_brasil_api, timeout=5.0)
        
        if response.status_code == 404:
            return json.dumps({"success": False, "error": "CEP não encontrado."})
            
        response.raise_for_status()
        data = response.json()
        
        return json.dumps({
            "success": True,
            "data": {
                "cep": data.get("cep"),
                "street": data.get("street") or data.get("logradouro"),
                "neighborhood": data.get("neighborhood") or data.get("bairro"),
                "city": data.get("city") or data.get("localidade"),
                "state": data.get("state") or data.get("uf")
            }
        })
            
    except Exception as e:
        print(f"[WARN] BrasilAPI lookup failed for {cep}: {e}")
        
        # Fallback to ViaCEP if BrasilAPI fails 
        try:
            url_viacep = f"https://viacep.com.br/ws/{clean_cep}/json/"
            response = requests.get(url_viacep, timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                if "erro" not in data:
                    return json.dumps({
                        "success": True,
                        "data": {
                            "cep": data.get("cep"),
                            "street": data.get("logradouro"),
                            "neighborhood": data.get("bairro"),
                            "city": data.get("localidade"),
                            "state": data.get("uf")
                        }
                    })
        except Exception as fallback_e:
            print(f"[WARN] ViaCEP fallback also failed: {fallback_e}")
            
        return json.dumps({"success": False, "error": "Falha de comunicação com o serviço de CEP (ViaCEP e BrasilAPI indisponíveis)."})
