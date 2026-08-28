# AWS Terraform deployment

This directory provisions one short-lived AWS deployment of the portfolio API. It demonstrates reproducible networking, compute, storage, IAM, bootstrap automation, verification, and cleanup without moving scientific workloads to cloud infrastructure.

## Architecture

- One VPC, internet gateway, public subnet, and route table
- One Amazon Linux 2023 `t3.small` EC2 instance
- Docker deployment pinned to the `v1.0.0-portfolio` application tag
- Port `8000` restricted to one workstation IPv4 `/32`
- No inbound SSH; administration uses AWS Systems Manager Session Manager
- One private, encrypted, versioned S3 bucket for runtime artifact synchronization
- An EC2 role limited to Session Manager and the bucket's `runtime/` prefix
- A 30-day lifecycle for demonstration artifacts

The S3 bucket uses `force_destroy = true` because the whole stack is intentionally ephemeral and must be removable with `terraform destroy`.

## Prerequisites

- Terraform 1.10 or newer
- AWS CLI 2.32 or newer
- An authenticated `terraform-runtime` profile backed by temporary `aws login` credentials
- A manually configured AWS budget

## Configure

From PowerShell:

```powershell
$env:AWS_PROFILE = "terraform-runtime"
$publicIp = (Invoke-RestMethod -Uri "https://checkip.amazonaws.com").Trim()

Copy-Item terraform.tfvars.example terraform.tfvars
(Get-Content terraform.tfvars).Replace("203.0.113.10/32", "$publicIp/32") |
    Set-Content terraform.tfvars
```

`terraform.tfvars` is intentionally ignored. Never commit credentials, API keys, account identifiers, or local state.

## Validate and review

```powershell
terraform fmt -recursive
terraform init
terraform validate
terraform plan -out deployment.tfplan
terraform show deployment.tfplan
```

Review the plan before applying it. A normal plan creates one EC2 instance, its networking and IAM resources, and one S3 bucket. It must not include EKS, RDS, NAT Gateway, load balancers, GPU instances, or autoscaling resources.

## Deploy and verify

```powershell
terraform apply deployment.tfplan
$healthUrl = terraform output -raw health_url
$capabilitiesUrl = terraform output -raw capabilities_url

Invoke-RestMethod -Uri $healthUrl
Invoke-RestMethod -Uri $capabilitiesUrl
```

Bootstrap can take several minutes while EC2 installs Docker and builds the Python image. If the endpoint is not ready, use the `session_manager_command` output and inspect:

```bash
sudo tail -n 200 /var/log/graphrag-bootstrap.log
sudo docker ps -a
sudo docker logs personal-graphrag-api
```

## Clean up

Capture non-sensitive evidence first, then remove all resources:

```powershell
terraform plan -destroy -out destruction.tfplan
terraform show destruction.tfplan
terraform apply destruction.tfplan
```

Apply the saved destruction plan only after confirming that it contains no additions or unrelated resources. Local state remains ignored and should be retained only until AWS confirms that every managed resource was deleted.

## Verified deployment

A complete deployment cycle was verified in `eu-north-1` on 2026-08-28:

- Terraform created the expected 17 resources without warnings.
- The API reported version `0.4.1`, healthy status, and a running dispatcher.
- `/capabilities` returned three registered domains: CAD simulation, cybersecurity, and drug discovery.
- The EC2 host registered as `Online` in Systems Manager without inbound SSH.
- Runtime SQLite state synchronized to the private S3 artifact prefix.
- A post-deployment plan returned no changes with detailed exit code `0`.
- The reviewed destruction plan removed all 17 resources and left an empty Terraform state.

This cycle verifies infrastructure provisioning, container deployment, API discovery, artifact synchronization, drift detection, and cleanup. Scientific executors remain on local or remote workers; this EC2 deployment does not move FreeCAD, OpenFOAM, Blender, docking, or molecular-dynamics workloads into AWS.

## Deferred work

Remote S3 state with native locking is deliberately deferred until after the first apply, verification, and destroy cycle. Kubernetes, Helm, RDS, GPU instances, autoscaling, and Ansible are outside this portfolio scope.
