##########################
#   VPC Endpoint DynamoDB  #
##########################
resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.dynamodb"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.vpc_rts.ids

  tags = {
    Name = "dynamodb-vpc-endpoint"
  }
}

##########################
#   VPC Endpoint S3        #
##########################
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = var.vpc_id
  service_name      = "com.amazonaws.${data.aws_region.current.name}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = data.aws_route_tables.vpc_rts.ids

  tags = {
    Name = "s3-vpc-endpoint"
  }
}
