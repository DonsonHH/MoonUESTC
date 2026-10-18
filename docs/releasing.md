# Maintainer release procedure

Builds and deployment acceptance run on the designated Linux release host. Edit and package source elsewhere if needed, without including private host records.

1. Update the version consistently; review notices and run scripts/audit-release.py.
2. Commit clean source and run scripts/build-release.sh on the Linux release host. PYTHON_BASE_IMAGE can use a verified official mirror digest. Dockerfile runs the unit suite before creating the non-root image.
3. Run scripts/verify-installation.py there, then validate the maintained instance upgrade with no active school jobs.
4. Tag the exact commit embedded in org.opencontainers.image.revision. Export the image, source and deploy bundle, and generate SHA256SUMS.release.txt. Artifacts contain no real user data or host addresses.
5. Upload MoonUESTC-vX.Y.Z-linux-amd64.image.tar.gz and checksums to a draft Release. Publish after acceptance.
6. The publish-image workflow checks this archive, source/revision/version/architecture labels, then pushes that same image to GHCR. It does not build or run the application and stores no release-server SSH key. Version, minor and latest tags are pushed.
7. First publication needs package visibility set to Public in GitHub settings. Verify anonymous pull and fresh installation from the public deploy bundle.

GITHUB_TOKEN grants contents:read and packages:write only to publishing. Repository visibility does not automatically make the image public. Current target is linux/amd64; add other architectures after actual build and deployment checks. Exclude .env, runtime directories, databases, keys, credentials and private deployment logs from all artifacts.
