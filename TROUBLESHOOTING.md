# Troubleshooting Guide

## Deployment Fails

1. **Check build logs:**
   ```bash
   doctl apps logs <APP_ID> --type build
   ```

2. **Check deployment logs:**
   ```bash
   doctl apps logs <APP_ID> --type deploy
   ```

3. **Common issues:**
   - Invalid GitHub repository path in `.do/app.yaml`
   - Missing dependencies in `requirements.txt`
   - Port mismatch (ensure app listens on `PORT` environment variable)
   - Ensure your app listens on `0.0.0.0`, not `localhost`

## Health Check Fails

1. Ensure your app exposes `/health` endpoint that returns 200 status
2. Check that app listens on `0.0.0.0`, not `localhost`
3. Verify port matches `http_port` in spec (default: 8080)
4. Increase `initial_delay_seconds` in health check config if app takes longer to start

**Example health check in `.do/app.yaml`:**
```yaml
health_check:
  http_path: /health
  initial_delay_seconds: 40
  period_seconds: 10
  timeout_seconds: 5
  success_threshold: 1
  failure_threshold: 3
```

## Process Won't Start

1. **Access console and check supervisord status:**
   ```bash
   supervisorctl status
   ```

2. **View process logs:**
   ```bash
   supervisorctl tail app stderr
   supervisorctl tail app stdout
   ```

3. **Check supervisord configuration:**
   ```bash
   cat /etc/supervisor/conf.d/supervisord.conf
   ```

4. **Common issues:**
   - Incorrect command in supervisord.conf
   - Missing file permissions
   - Dependencies not installed
   - Process exits immediately (check `startsecs` setting)

## Processes Restart Frequently

Check `startsecs` in supervisord.conf - the process must stay running this long to be considered successfully started.

```ini
[program:app]
startsecs=10  # Process must run for 10 seconds to be considered started
```

## Auto-Deploy Not Working

**Problem**: Pushing to GitHub doesn't trigger deployment

**Solution:**
- Check `deploy_on_push: true` in `.do/app.yaml`
- Verify GitHub integration in App Platform console
- Check build logs for errors
- Ensure you're pushing to the correct branch specified in the spec

## Production Considerations

### Security

- **Never commit secrets** to the repository
- Use App Platform environment variables with `type: SECRET` for sensitive data
- Keep dependencies updated regularly
- Use specific version tags in Dockerfile instead of `latest`
- Review and restrict file permissions in your container

### Monitoring

- Use App Platform's built-in metrics for container health
- Configure logging forwarding to centralized logging systems
- Set up alerts for container restarts and health check failures
- Monitor resource usage (CPU, memory) and scale accordingly

### Performance

- Use specific version tags for all dependencies
- Optimize Docker image size by removing unnecessary packages
- Consider using multi-stage builds for smaller images
- Configure appropriate resource limits in app spec
