# TODO

* When register new product using barcode and fetch from OFF: Search for dublicate by EAN and name. 
* * if dublicate found and allready synced with off: Error
* * if dublicate found and not synced with off: overwrite
* When register new product using name Search for dublicate name. 
* * if dublicate found and allready synced with off: Error
* * if dublicate found and not synced with off: ask for merge
* When editing a product and fetch from OFF: Search for dublicate by EAN and name. 
* * if dublicate found and allready synced with off: ask for delete dupplicate
* * if dublicate found and not synced with off: ask for merge
* Import products must have settings for
* * Search OFF (if is_synced_with_off flag is not set)
* * * Search by name and EAN (default)
* * * Search by EAN 
* * * Search by name 
* * Dublicate check (this must happen after OFF serach if enabled): Search for dublicate by EAN and name. - This setting should be deufalt onn
* * * if dublicate found and allready synced with off: Skip/merge/duplicate - merge should be default
* * * if dublicate found and not synced with off: Skip/merge/duplicate - merge should be default