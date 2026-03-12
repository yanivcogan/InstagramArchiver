alter table account
    add identifiers json null;


UPDATE account a
LEFT JOIN (
  SELECT
    canonical_id,
    CONCAT(
      '[',
      GROUP_CONCAT(DISTINCT JSON_QUOTE(value) SEPARATOR ','),
      ']'
    ) AS identifiers
  FROM (
    SELECT canonical_id, CONCAT('url_', url) AS value
    FROM account_archive
    WHERE url IS NOT NULL
    UNION ALL
    SELECT canonical_id, CONCAT('id_', id_on_platform) AS value
    FROM account_archive
    WHERE id_on_platform IS NOT NULL
  ) AS t
  GROUP BY canonical_id
) s ON s.canonical_id = a.id
SET a.identifiers = COALESCE(s.identifiers, '[]');