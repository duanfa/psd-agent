USE psd_agent;

ALTER TABLE workflow_runs
  ADD COLUMN IF NOT EXISTS task_code VARCHAR(100) NULL AFTER current_stage_icon,
  ADD COLUMN IF NOT EXISTS task_type VARCHAR(100) NULL AFTER task_code;

ALTER TABLE workflow_runs
  ADD INDEX IF NOT EXISTS ix_workflow_runs_task_code (task_code);

CREATE TABLE IF NOT EXISTS app_settings (
  `key` VARCHAR(100) NOT NULL,
  value_json JSON NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS brand_training_tasks (
  id INT NOT NULL AUTO_INCREMENT,
  brand_id INT NULL,
  task_code VARCHAR(100) NOT NULL,
  title VARCHAR(255) NOT NULL,
  status VARCHAR(64) NOT NULL,
  summary TEXT NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uq_brand_training_tasks_task_code (task_code),
  KEY ix_brand_training_tasks_brand_id (brand_id),
  KEY ix_brand_training_tasks_task_code (task_code),
  KEY ix_brand_training_tasks_status (status),
  CONSTRAINT fk_brand_training_tasks_brand_id
    FOREIGN KEY (brand_id) REFERENCES brands(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS brand_rules (
  id INT NOT NULL AUTO_INCREMENT,
  brand_id INT NULL,
  version VARCHAR(64) NOT NULL,
  status VARCHAR(64) NOT NULL DEFAULT 'draft',
  rule_count INT NOT NULL DEFAULT 0,
  layout_count INT NOT NULL DEFAULT 0,
  prompt_count INT NOT NULL DEFAULT 0,
  design_rules JSON NULL,
  layout_rules JSON NULL,
  components JSON NULL,
  prompt_templates JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_brand_rules_brand_id (brand_id),
  KEY ix_brand_rules_version (version),
  CONSTRAINT fk_brand_rules_brand_id
    FOREIGN KEY (brand_id) REFERENCES brands(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS products (
  id INT NOT NULL AUTO_INCREMENT,
  brand_id INT NULL,
  name VARCHAR(255) NOT NULL,
  category VARCHAR(100) NOT NULL DEFAULT '',
  summary TEXT NOT NULL,
  brief TEXT NOT NULL,
  design_direction TEXT NOT NULL,
  selling_points JSON NULL,
  materials JSON NULL,
  selling_point_count INT NOT NULL DEFAULT 0,
  asset_count INT NOT NULL DEFAULT 0,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_products_brand_id (brand_id),
  KEY ix_products_name (name),
  CONSTRAINT fk_products_brand_id
    FOREIGN KEY (brand_id) REFERENCES brands(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
