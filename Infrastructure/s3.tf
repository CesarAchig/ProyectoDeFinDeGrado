###########################
#      Filetransfer S3    #
###########################
resource "aws_s3_bucket" "filestransfer_bucket" {
  bucket = var.filestransfer_s3.name
  tags = {
    "Name" = var.filestransfer_s3.name
  }
}

resource "aws_s3_object" "training_service_code_upload" {
  bucket      = aws_s3_bucket.filestransfer_bucket.bucket
  key         = reverse(split("/", data.archive_file.zip_code_training.output_path))[0]
  source      = "${var.temporal_folder}/${local.training_service_zip_name}"
  source_hash = data.archive_file.zip_code_training.output_base64sha256
}

resource "aws_s3_object" "api_listener_code_upload" {
  bucket      = aws_s3_bucket.filestransfer_bucket.bucket
  key         = reverse(split("/", data.archive_file.zip_api_code.output_path))[0]
  source      = "${var.temporal_folder}/${local.listener_rest_zip_name}"
  source_hash = data.archive_file.zip_api_code.output_base64sha256
}

resource "aws_s3_object" "common_code_upload" {
  bucket      = aws_s3_bucket.filestransfer_bucket.bucket
  key         = reverse(split("/", data.archive_file.zip_code_common.output_path))[0]
  source      = "${var.temporal_folder}/${local.common_code_zip_name}"
  source_hash = data.archive_file.zip_code_common.output_base64sha256
}


###########################
#       Datasets S3       #   
###########################
resource "aws_s3_bucket" "dataset_bucket" {
  bucket = var.datasets_s3.name
  tags = {
    Name = var.datasets_s3.name
  }
}

##########################
#        MlFlow S3       #   
##########################
resource "aws_s3_bucket" "mlflow_artifacts_bucket" {
  bucket = var.mlflow_artifacts_s3.name
  tags = {
    Name = var.mlflow_artifacts_s3.name
  }
}

