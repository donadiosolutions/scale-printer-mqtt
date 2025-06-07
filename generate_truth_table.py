import os
import yaml

def get_workflow_files():
    """Get all YAML files in the .github/workflows directory."""
    workflows_dir = '.github/workflows'
    if not os.path.exists(workflows_dir):
        return []
    return [os.path.join(workflows_dir, f) for f in os.listdir(workflows_dir) if f.endswith('.yml')]

def parse_workflow(file_path):
    """Parse a workflow file."""
    with open(file_path, 'r') as f:
        return yaml.safe_load(f)

def get_platforms_for_event(event, ref):
    """Determine the platforms for a given event."""
    if event == 'workflow_dispatch':
        return ['amd64', 'arm64']  # Both are possible
    if event == 'release':
        return ['amd64', 'arm64']
    if event == 'push' and ref == 'refs/heads/master':
        return ['amd64', 'arm64']
    if event == 'pull_request':
        return ['amd64']
    return ['amd64'] # Default for other events

def generate_truth_table(workflows):
    """Generate the truth table."""
    table = []
    table.append("| Workflow | Job | Step | Event | amd64 | arm64 |")
    table.append("|---|---|---|---|---|---|")

    for file_path in workflows:
        workflow_name = os.path.basename(file_path)
        try:
            workflow = parse_workflow(file_path)
            if not workflow or 'jobs' not in workflow:
                continue

            for job_name, job in workflow.get('jobs', {}).items():
                steps = job.get('steps', [])
                if not steps:
                    continue

                on = workflow.get('on', {})
                events = []
                if 'push' in on:
                    events.append(('push', 'refs/heads/master'))
                if 'pull_request' in on:
                    events.append(('pull_request', ''))
                if 'release' in on:
                    events.append(('release', ''))
                if 'workflow_dispatch' in on:
                    events.append(('workflow_dispatch', ''))
                if not events:
                    events.append(('(called)', ''))


                for step in steps:
                    step_name = step.get('name', 'N/A')
                    for event, ref in events:
                        platforms = get_platforms_for_event(event, ref)
                        amd64 = '✅' if 'amd64' in platforms else '❌'
                        arm64 = '✅' if 'arm64' in platforms else '❌'
                        if workflow_name == 'codeql.yml':
                            amd64 = 'N/A'
                            arm64 = 'N/A'
                        table.append(f"| `{workflow_name}` | `{job_name}` | `{step_name}` | {event} | {amd64} | {arm64} |")
        except yaml.YAMLError as e:
            print(f"Error parsing {file_path}: {e}")


    return "\n".join(table)

def main():
    """Main function."""
    workflow_files = get_workflow_files()
    truth_table = generate_truth_table(workflow_files)
    with open('TESTS.md', 'w') as f:
        f.write("# Workflow Platform Truth Table\n\n")
        f.write("This table shows which architectures are built for each step in each workflow, based on the triggering event.\n\n")
        f.write(truth_table)

if __name__ == "__main__":
    main()
