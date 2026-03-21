CREATE TABLE incorporation_job (
      id            INT AUTO_INCREMENT PRIMARY KEY,
      started_at    DATETIME NOT NULL,
      completed_at  DATETIME,
      status        ENUM('running','completed','failed') NOT NULL DEFAULT 'running',
      triggered_by_user_id INT,
      triggered_by_ip      VARCHAR(255),
      log           MEDIUMTEXT,   -- full log snapshot written at completion
      error         TEXT
  );