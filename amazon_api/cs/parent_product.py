# -*- encoding: utf-8 -*-

a = {'status': {'value': 'Success'}, 'IdType': {'value': 'ASIN'}, 'Products': {'Product': {'Relationships': {'VariationChild': [{'Color': {'value': '1'}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B078MKFVMV'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'Size': {'value': '56-59cm'}}, {'Color': {'value': '2'}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B078MJDJQ3'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'Size': {'value': '56-59cm'}}, {'Color': {'value': '3'}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B078MF4GDH'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'Size': {'value': '56-59cm'}}, {'Color': {'value': '4'}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B078MCD3FF'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'Size': {'value': '56-59cm'}}, {'Color': {'value': '5'}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B078MGQKKD'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'Size': {'value': '56-59cm'}}, {'Color': {'value': '6'}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B078MHX1LT'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'Size': {'value': '56-59cm'}}]}, 'Identifiers': {'MarketplaceASIN': {'ASIN': {'value': 'B078MHTSTV'}, 'MarketplaceId': {'value': 'ATVPDKIKX0DER'}}}, 'SalesRankings': {'SalesRank': {'ProductCategoryId': {'value': 'sports_display_on_website'}, 'Rank': {'value': '934110'}}}, 'AttributeSets': {'ItemAttributes': {'lang': {'value': 'en-US'}, 'Publisher': {'value': 'XZP'}, 'Title': {'value': 'XZP 100% Hemp Wool Wide Brim Winter Autumn Floppy Felt Trilby fedora Hat For Elegant Womem Men Top Cloche Panama Church Cap'}, 'Brand': {'value': 'XZP'}, 'SmallImage': {'URL': {'value': 'http://ecx.images-amazon.com/images/I/41eAii2fBoL._SL75_.jpg'}, 'Width': {'Units': {'value': 'pixels'}, 'value': '75'}, 'Height': {'Units': {'value': 'pixels'}, 'value': '75'}}, 'Binding': {'value': 'Misc.'}, 'ProductGroup': {'value': 'Sports'}, 'Label': {'value': 'XZP'}, 'ProductTypeName': {'value': 'SPORTING_GOODS'}, 'Studio': {'value': 'XZP'}, 'NumberOfItems': {'value': '1'}, 'PackageQuantity': {'value': '1'}, 'PartNumber': {'value': 'XZP'}, 'Manufacturer': {'value': 'XZP'}}}}}, 'Id': {'value': 'B078MHTSTV'}}
# print a.keys()

Products = a.get('Products', {})
Product = Products.get('Product', {})
Identifiers = Product.get('Identifiers', {})
SalesRankings = Product.get('SalesRankings', {})
AttributeSets = Product.get('AttributeSets', {})
print 'IdType:',a.get('IdType', {})
print 'Id:',a.get('Id', {})
print 'Identifiers:',Identifiers
print 'SalesRankings:',SalesRankings
print 'AttributeSets:',AttributeSets
ItemAttributes = AttributeSets.get('ItemAttributes', {})
for (key, val) in ItemAttributes.items():
    print key,':',val
VariationChild = a.get('Products', {}).get('Product', {}).get('Relationships', {}).get('VariationChild', [])
if type(VariationChild) is not list:
    VariationChild = [VariationChild]
for child in VariationChild:
    print 'child:',child
