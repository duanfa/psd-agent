CREATE DATABASE IF NOT EXISTS psd_agent
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE psd_agent;

CREATE TABLE IF NOT EXISTS app_settings (
  `key` VARCHAR(100) NOT NULL,
  value_json JSON NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS brands (
  id INT NOT NULL AUTO_INCREMENT,
  name VARCHAR(255) NOT NULL,
  status VARCHAR(64) NOT NULL DEFAULT 'active',
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_brands_name (name),
  KEY ix_brands_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workflow_runs (
  run_id VARCHAR(100) NOT NULL,
  status VARCHAR(64) NOT NULL,
  current_stage VARCHAR(100) NULL,
  current_stage_title VARCHAR(255) NULL,
  current_stage_icon VARCHAR(64) NULL,
  task_code VARCHAR(100) NULL,
  task_type VARCHAR(100) NULL,
  project_name VARCHAR(255) NULL,
  brand_name VARCHAR(255) NULL,
  product_name VARCHAR(255) NULL,
  workflow_mode VARCHAR(64) NULL,
  request_payload JSON NULL,
  summary TEXT NULL,
  used_deepagents BOOLEAN NOT NULL DEFAULT FALSE,
  agent_report LONGTEXT NULL,
  design_spec JSON NULL,
  warnings JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  completed_at DATETIME NULL,
  PRIMARY KEY (run_id),
  KEY ix_workflow_runs_task_code (task_code),
  KEY ix_workflow_runs_status (status),
  KEY ix_workflow_runs_brand_name (brand_name)
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

CREATE TABLE IF NOT EXISTS brand_assets (
  id INT NOT NULL AUTO_INCREMENT,
  brand_id INT NULL,
  name VARCHAR(255) NOT NULL,
  folder VARCHAR(64) NOT NULL,
  content_type VARCHAR(255) NULL,
  size BIGINT NOT NULL DEFAULT 0,
  saved_path VARCHAR(1024) NULL,
  source VARCHAR(255) NULL,
  status VARCHAR(64) NOT NULL DEFAULT 'uploaded',
  extracted_text LONGTEXT NULL,
  metadata_json JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_brand_assets_brand_id (brand_id),
  KEY ix_brand_assets_name (name),
  KEY ix_brand_assets_folder (folder),
  CONSTRAINT fk_brand_assets_brand_id
    FOREIGN KEY (brand_id) REFERENCES brands(id)
    ON DELETE SET NULL
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workflow_assets (
  id INT NOT NULL AUTO_INCREMENT,
  run_id VARCHAR(100) NOT NULL,
  name VARCHAR(255) NOT NULL,
  content_type VARCHAR(255) NULL,
  size BIGINT NOT NULL DEFAULT 0,
  saved_path VARCHAR(1024) NULL,
  bucket VARCHAR(64) NOT NULL,
  extracted_text LONGTEXT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_workflow_assets_run_id (run_id),
  KEY ix_workflow_assets_bucket (bucket),
  CONSTRAINT fk_workflow_assets_run_id
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workflow_stages (
  id INT NOT NULL AUTO_INCREMENT,
  run_id VARCHAR(100) NOT NULL,
  stage_id VARCHAR(100) NOT NULL,
  title VARCHAR(255) NOT NULL,
  icon VARCHAR(64) NOT NULL DEFAULT 'sparkles',
  status VARCHAR(64) NOT NULL,
  summary TEXT NOT NULL,
  detail LONGTEXT NOT NULL,
  data JSON NOT NULL,
  used_model BOOLEAN NOT NULL DEFAULT FALSE,
  elapsed_ms INT NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_workflow_stage_run_stage (run_id, stage_id),
  KEY ix_workflow_stages_run_id (run_id),
  KEY ix_workflow_stages_stage_id (stage_id),
  KEY ix_workflow_stages_status (status),
  CONSTRAINT fk_workflow_stages_run_id
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workflow_logs (
  id INT NOT NULL AUTO_INCREMENT,
  run_id VARCHAR(100) NOT NULL,
  scope VARCHAR(100) NOT NULL,
  title TEXT NOT NULL,
  message LONGTEXT NOT NULL,
  payload JSON NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_workflow_logs_run_id (run_id),
  CONSTRAINT fk_workflow_logs_run_id
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS workflow_artifacts (
  id INT NOT NULL AUTO_INCREMENT,
  run_id VARCHAR(100) NOT NULL,
  output_dir VARCHAR(1024) NOT NULL,
  preview_svg VARCHAR(1024) NOT NULL,
  design_spec_path VARCHAR(1024) NOT NULL,
  photoshop_jsx VARCHAR(1024) NOT NULL,
  readme VARCHAR(1024) NOT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY ix_workflow_artifacts_run_id (run_id),
  CONSTRAINT fk_workflow_artifacts_run_id
    FOREIGN KEY (run_id) REFERENCES workflow_runs(run_id)
    ON DELETE CASCADE
    ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
