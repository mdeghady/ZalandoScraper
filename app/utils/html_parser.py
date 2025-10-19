import json
import re
from bs4 import BeautifulSoup
from typing import List, Dict

def extract_merchant_data(html: str , product_id : str) -> List[Dict]:
    """Extract all merchant JSON data from the given HTML content."""

    soup = BeautifulSoup(html, "lxml")
    top_div = soup.find("div", class_="x7LsVH")
    scripts = top_div.find_all("script", id=re.compile(r"^re-ph"))

    # Select the first script tag
    cache_idx = str(scripts[0]).index('cache')

    # Clean the script tag
    closing_script_idx = str(scripts[0]).index('</script>')
    retrieved_data = str(scripts[0])[cache_idx - 2:closing_script_idx - 14]

    data_dict = json.loads(retrieved_data)['cache']
    query_key = (
    f'{{"id":"b11e5482aaf960948f5c738fdbc930d646d74531e57381722c621491826959f8",'
    f'"variables":{{"id":"ern:product::{product_id}"}},'
    f'"extra":{{}}}}'
    )
    product_simples = data_dict[query_key]['data']['product']['simples']

    # Extract text for every sku e.g., {'sku12355' : 'Venduto da Timberland , spedito da Zalando.}
    sku_to_merchant_text = []
    for simple in product_simples:
        simple_sku = simple.get('sku' , "")
        simple_merchant_data = simple.get('allOffers',{})[0].get('fulfillmentLabel',{})
        if simple_sku and simple_merchant_data:
            sku_to_merchant_text.append({"sku" : simple_sku,
                                         "merchant_data" : simple_merchant_data.get('label')})

    sku_to_merchant_data = dict()
    for simple in sku_to_merchant_text:
        sku = simple['sku']
        merchant_dict = simple['merchant_data'] #list of dicts
        if len(merchant_dict) == 4:
            merchant_info = {
                "merchant" : merchant_dict[1].get("text"),
                "shipper" : merchant_dict[2].get("text").split(" ")[-1]
            }
        elif len(merchant_dict) == 3 or len(merchant_dict) == 2:
            merchant_info = {
                "merchant" : merchant_dict[1].get("text"),
                "shipper" : merchant_dict[1].get("text")
            }
        else:
            merchant_info = {
                "merchant" : None,
                "shipper" : None
            }
        sku_to_merchant_data[sku] =  merchant_info
    return sku_to_merchant_data

def extract_stock_data(html: str , product_id : str) -> List[Dict]:
    """Extract all merchant JSON data from the given HTML content."""

    soup = BeautifulSoup(html, "lxml")
    top_div = soup.find("div", class_="x7LsVH")
    scripts = top_div.find_all("script", id=re.compile(r"^re-ph"))

    # Select the first script tag
    cache_idx = str(scripts[0]).index('cache')

    # Clean the script tag
    closing_script_idx = str(scripts[0]).index('</script>')
    retrieved_data = str(scripts[0])[cache_idx - 2:closing_script_idx - 14]

    data_dict = json.loads(retrieved_data)['cache']

    query_key = (f'{{"id":"a93ea1d4d2901d1dca65ce7796293f177db5a6be619c624e69d27245362e0b7b",'
                 f'"variables":{{"id":"ern:product::{product_id}",'
                 f'"shouldUseOldPriceDisplayForUI":true}},"extra":{{}}}}')
    stock_data = data_dict[query_key]['data']['product']['simples'][0]['allOffers'][0]['stock']['quantity']
    sku = data_dict[query_key]['data']['product']['simples'][0]['sku']
    return {
        "sku": sku,
        "stock": stock_data
    }
