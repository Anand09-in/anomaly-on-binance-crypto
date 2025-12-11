module "vpc" {
  source = "./vpc"
  project_name  = var.project_name
}

module "s3" {
  source         = "./s3"
  project_name= var.project_name
}

module "mlflow" {
  source            = "./mlflow"
  allowed_ip        = var.allowed_ip
  project_name      = var.project_name
  region            = var.region
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.subnet_ids
}

module "ecr" {
  source         = "./ecr"
  project_name = var.project_name
}

module "eks" {
  source                = "./eks"
  eks_cluster_name      = var.eks_cluster_name
  node_group_size       = var.node_group_size
  node_group_instances  = var.node_group_instance_types
  project_name          = var.project_name
  region                = var.region
  vpc_id                = module.vpc.vpc_id
  subnet_ids            = module.vpc.subnet_ids
}


module "kafka" {
  source            = "./kafka"
  project_name      = var.project_name
  vpc_id            = module.vpc.vpc_id
  vpc_cidr          = module.vpc.cidr_block
  public_subnet_id  = module.vpc.public_subnet_a_id
  allowed_ip        = var.allowed_ip
  key_name          = var.key_name
}
