UPDATE media
SET annotation = LOWER(JSON_UNQUOTE(JSON_EXTRACT(data, '$.accessibility_caption')))
WHERE TRUE