# Table creation

```sql
CREATE TABLE `grading_request` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `homework_id` int(11) DEFAULT NULL,
  `student` varchar(512) DEFAULT NULL,
  `input_id_gcs` varchar(512) DEFAULT NULL,
  `created_on` datetime DEFAULT NULL,
  `request_nonce` varchar(512) DEFAULT NULL,
  `completed` char(1) DEFAULT NULL,
  `grade` float DEFAULT NULL,
  `delay` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `homework_id__idx` (`homework_id`),
  KEY `grading_request_nonce_idx` (`request_nonce`),
  KEY `grading_request_student_idx` (`student`),
  CONSTRAINT `grading_request_ibfk_1` FOREIGN KEY (`homework_id`) REFERENCES `homework` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=5663 DEFAULT CHARSET=utf8mb4;
```

```sql
CREATE TABLE `grade` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `student` varchar(512) DEFAULT NULL,
  `assignment_id` int(11) DEFAULT NULL,
  `grade_date` datetime DEFAULT NULL,
  `homework_id` int(11) DEFAULT NULL,
  `grade` float DEFAULT NULL,
  `drive_id` varchar(512) DEFAULT NULL,
  `submission_id_gcs` varchar(512) DEFAULT NULL,
  `feedback_id_gcs` varchar(512) DEFAULT NULL,
  `is_valid` char(1) DEFAULT NULL,
  `cell_id_to_points` varchar(16384) DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `assignment_id__idx` (`assignment_id`),
  KEY `homework_id__idx` (`homework_id`),
  KEY `grade_homework_idx` (`homework_id`),
  CONSTRAINT `grade_ibfk_1` FOREIGN KEY (`assignment_id`) REFERENCES `assignment` (`id`) ON DELETE CASCADE,
  CONSTRAINT `grade_ibfk_2` FOREIGN KEY (`homework_id`) REFERENCES `homework` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=5332 DEFAULT CHARSET=utf8
```


```sql
CREATE TABLE `ai_feedback_request` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `grade_id` int(11) DEFAULT NULL,
  `student` varchar(512) DEFAULT NULL,
  `created_on` datetime DEFAULT NULL,
  `request_nonce` varchar(512) DEFAULT NULL,
  `completed` char(1) DEFAULT NULL,
  `delay` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `grade_id__idx` (`grade_id`),
  KEY `ai_feedback_request_nonce_idx` (`request_nonce`),
  CONSTRAINT `ai_feedback_request_ibfk_1` FOREIGN KEY (`grade_id`) REFERENCES `grade` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

```sql
CREATE TABLE `ai_feedback` (
  `id` int(11) NOT NULL AUTO_INCREMENT,
  `grade_id` int(11) DEFAULT NULL,
  `student` varchar(512) DEFAULT NULL,
  `created_on` datetime DEFAULT NULL,
  `ai_feedback_id_gcs` varchar(512) DEFAULT NULL,
  `ai_feedback_id_drive` varchar(512) DEFAULT NULL,
  `model_used` varchar(512) DEFAULT NULL,
  `cost_information` varchar(512) DEFAULT NULL,
  `rating` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `grade_id__idx` (`grade_id`),
  CONSTRAINT `ai_feedback_ibfk_1` FOREIGN KEY (`grade_id`) REFERENCES `grade` (`id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

```sql
ALTER TABLE `assignment` ADD `ai_feedback` INT(11);
```

