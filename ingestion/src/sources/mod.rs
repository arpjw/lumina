pub mod edgar;
pub mod fred;
pub mod gdelt;
pub mod reddit;
pub mod wikipedia;

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RawRecord {
    pub id: String,
    pub source: String,
    pub source_type: String,
    pub timestamp: DateTime<Utc>,
    pub title: Option<String>,
    pub body: String,
    pub url: Option<String>,
    pub metadata: serde_json::Value,
}
