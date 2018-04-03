# -*- encoding: utf-8 -*-

a = {'status': {'value': 'Success'}, 'IdType': {'value': 'SellerSKU'}, 'Products': {'Product': {'Relationships': {'VariationChild': {'Color': {'value': 'blue'}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B07921RTZW'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}}}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B079BKWHW7'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'SalesRankings': {}, 'AttributeSets': {'ItemAttributes': {'lang': {'value': 'en-US'}, 'Publisher': {'value': 'abc'}, 'Title': {'value': 'ds shop ljp test three ds shop'}, 'Brand': {'value': 'XZP'}, 'SmallImage': {'URL': {'value': 'http://ecx.images-amazon.com/images/I/51VCsm%2Brf7L._SL75_.jpg'}, 'Width': {'Units': {'value': 'pixels'}, 'value': '75'}, 'Height': {'Units': {'value': 'pixels'}, 'value': '47'}}, 'Binding': {'value': 'Electronics'}, 'ProductGroup': {'value': 'CE'}, 'Label': {'value': 'abc'}, 'ProductTypeName': {'value': 'CONSUMER_ELECTRONICS'}, 'Studio': {'value': 'abc'}, 'NumberOfItems': {'value': '1'}, 'PackageQuantity': {'value': '1'}, 'Manufacturer': {'value': 'abc'}}}}}, 'Id': {'value': 'CAAA'}}

Products = a.get('Products', {})
Product = a.get('Products', {}).get('Product', {})
Relationships = Product.get('Relationships', {})
VariationChild = Relationships.get('VariationChild', {})
# print Relationships
# sku = a.get('Id', {}).get('value', '')
# asin = a.get('Products', {}).get('Product', {}).get('Identifiers', {}).get('MarketplaceASIN', {}).get('ASIN', {}).get('value', '')
# print sku,asin

