# -*- encoding: utf-8 -*-


a = {'status': {'value': 'Success'}, 'IdType': {'value': 'ASIN'}, 'Products': {'Product': {'Relationships': {'VariationParent': {'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B077PQ5YJH'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}}}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B077MXG33Y'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'SalesRankings': {}, 'AttributeSets': {'ItemAttributes': {'lang': {'value': 'en-US'}, 'Publisher': {'value': 'XZP'}, 'Title': {'value': 'XZP 5M 50LED Outdoor Christmas Fairy Lights Cool White Warm White Copper Wire LED Starry Lights Fairy LED String Light Decoration DC 12V ( Color : Cool White )'}, 'Color': {'value': 'Cool White'}, 'Brand': {'value': 'XZP'}, 'SmallImage': {'URL': {'value': 'http://ecx.images-amazon.com/images/I/51EBUvCCgRL._SL75_.jpg'}, 'Width': {'Units': {'value': 'pixels'}, 'value': '75'}, 'Height': {'Units': {'value': 'pixels'}, 'value': '75'}}, 'Binding': {'value': 'Kitchen'}, 'ProductGroup': {'value': 'Home'}, 'Label': {'value': 'XZP'}, 'ProductTypeName': {'value': 'HOME'}, 'Studio': {'value': 'XZP'}, 'NumberOfItems': {'value': '1'}, 'PackageQuantity': {'value': '1'}, 'PartNumber': {'value': 'XZP'}, 'PackageDimensions': {'Width': {'Units': {'value': 'inches'}, 'value': '3.94'}, 'Length': {'Units': {'value': 'inches'}, 'value': '5.91'}, 'Height': {'Units': {'value': 'inches'}, 'value': '0.79'}}, 'Manufacturer': {'value': 'XZP'}}}}}, 'Id': {'value': 'B077MXG33Y'}}
Products = a.get('Products', {})
Product = Products.get('Product', {})
Identifiers = Product.get('Identifiers', {})
SalesRankings = Product.get('SalesRankings', {})
AttributeSets = Product.get('AttributeSets', {})
print 'IdType:',a.get('IdType', {})
print 'Id:',a.get('Id', {})
print 'Identifiers:',Identifiers
print 'SalesRankings:',SalesRankings
# print 'AttributeSets:',AttributeSets.keys()
ItemAttributes = AttributeSets.get('ItemAttributes', {})
for (key, val) in ItemAttributes.items():
    print key,':',val
VariationChild = a.get('Products', {}).get('Product', {}).get('Relationships', {}).get('VariationChild', [])
if type(VariationChild) is not list:
    VariationChild = [VariationChild]
for child in VariationChild:
    print 'child:',child