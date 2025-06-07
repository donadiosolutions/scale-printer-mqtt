#!/usr/bin/env python3
"""
Generate a comprehensive truth table for GitHub Actions workflow execution
showing which steps run on which platforms for different events.
"""

import os
import yaml
import json
from typing import Dict, List, Tuple, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

class EventType(Enum):
    PUSH_MASTER = "push_master"
    PULL_REQUEST = "pull_request"
    MERGE_GROUP = "merge_group"
    RELEASE = "release"
    WORKFLOW_DISPATCH_AMD64_ONLY = "workflow_dispatch_amd64_only"
    WORKFLOW_DISPATCH_ARM64_ONLY = "workflow_dispatch_arm64_only"
    WORKFLOW_DISPATCH_BOTH = "workflow_dispatch_both"

@dataclass
class StepExecution:
    workflow_file: str
    workflow_name: str
    job_name: str
    step_name: str
    event: EventType
    amd64: bool
    arm64: bool
    condition: str = ""
    matrix_values: Dict[str, Any] = None

class WorkflowAnalyzer:
    def __init__(self):
        self.workflows = {}
        self.step_executions = []

    def load_workflows(self):
        """Load all workflow files."""
        workflows_dir = '.github/workflows'
        if not os.path.exists(workflows_dir):
            return

        for filename in os.listdir(workflows_dir):
            if filename.endswith('.yml') or filename.endswith('.yaml'):
                filepath = os.path.join(workflows_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        workflow = yaml.safe_load(f)
                        self.workflows[filename] = workflow
                except Exception as e:
                    print(f"Error loading {filename}: {e}")

    def get_platforms_for_event(self, event: EventType) -> List[str]:
        """Determine platforms based on event type and build.yml logic."""
        if event == EventType.WORKFLOW_DISPATCH_AMD64_ONLY:
            return ['linux/amd64']
        elif event == EventType.WORKFLOW_DISPATCH_ARM64_ONLY:
            return ['linux/arm64']
        elif event == EventType.WORKFLOW_DISPATCH_BOTH:
            return ['linux/amd64', 'linux/arm64']
        elif event == EventType.RELEASE:
            return ['linux/amd64', 'linux/arm64']
        elif event == EventType.PUSH_MASTER:
            return ['linux/amd64', 'linux/arm64']
        else:  # pull_request, merge_group, other
            return ['linux/amd64']

    def evaluate_condition(self, condition: str, event: EventType, context: Dict) -> bool:
        """Evaluate GitHub Actions conditional expressions."""
        if not condition:
            return True

        # Handle common conditions
        if "github.event_name != 'release'" in condition:
            return event != EventType.RELEASE
        elif "github.event_name == 'release'" in condition:
            return event == EventType.RELEASE
        elif "github.event_name == 'workflow_dispatch'" in condition:
            return event.name.startswith('WORKFLOW_DISPATCH')
        elif "github.ref == 'refs/heads/master'" in condition:
            return event == EventType.PUSH_MASTER

        # Default to true for complex conditions we can't easily evaluate
        return True

    def get_workflow_events(self, workflow: Dict) -> List[EventType]:
        """Get all possible events that can trigger a workflow."""
        events = []
        # YAML parser converts 'on' to boolean True, so check both
        on_config = workflow.get('on', workflow.get(True, {}))

        if isinstance(on_config, str):
            # Simple string event
            if on_config == 'push':
                events.append(EventType.PUSH_MASTER)
        elif isinstance(on_config, dict):
            if 'push' in on_config:
                push_config = on_config['push']
                if isinstance(push_config, dict) and 'branches' in push_config:
                    if 'master' in push_config['branches']:
                        events.append(EventType.PUSH_MASTER)
                else:
                    events.append(EventType.PUSH_MASTER)

            if 'pull_request' in on_config:
                events.append(EventType.PULL_REQUEST)

            if 'merge_group' in on_config:
                events.append(EventType.MERGE_GROUP)

            if 'release' in on_config:
                events.append(EventType.RELEASE)

            if 'workflow_dispatch' in on_config:
                # For workflow_dispatch, we need to consider all input combinations
                dispatch_config = on_config['workflow_dispatch']
                if isinstance(dispatch_config, dict) and 'inputs' in dispatch_config:
                    inputs = dispatch_config['inputs']
                    if 'build_amd64' in inputs and 'build_arm64' in inputs:
                        events.extend([
                            EventType.WORKFLOW_DISPATCH_AMD64_ONLY,
                            EventType.WORKFLOW_DISPATCH_ARM64_ONLY,
                            EventType.WORKFLOW_DISPATCH_BOTH
                        ])
                    else:
                        events.append(EventType.WORKFLOW_DISPATCH_BOTH)
                else:
                    events.append(EventType.WORKFLOW_DISPATCH_BOTH)

        # Handle workflow_call (these are called by other workflows)
        if isinstance(on_config, dict) and 'workflow_call' in on_config:
            # These will be analyzed when processing the calling workflow
            pass

        return events if events else [EventType.PUSH_MASTER]  # Default

    def expand_matrix(self, matrix_config: Dict, platforms: List[str]) -> List[Dict]:
        """Expand matrix configuration into individual combinations."""
        if not matrix_config:
            return [{}]

        # Handle include/exclude later, for now just do basic expansion
        combinations = [{}]

        for key, values in matrix_config.items():
            if key in ['include', 'exclude']:
                continue

            new_combinations = []
            for combo in combinations:
                if key == 'platform':
                    # Special handling for platform matrix - use actual platforms
                    if isinstance(values, str) and '${{' in values:
                        # Dynamic platform from determine_platforms job
                        for platform in platforms:
                            new_combo = combo.copy()
                            new_combo[key] = platform
                            new_combinations.append(new_combo)
                    elif isinstance(values, list):
                        for value in values:
                            new_combo = combo.copy()
                            new_combo[key] = value
                            new_combinations.append(new_combo)
                    else:
                        new_combo = combo.copy()
                        new_combo[key] = values
                        new_combinations.append(new_combo)
                elif isinstance(values, list):
                    for value in values:
                        new_combo = combo.copy()
                        new_combo[key] = value
                        new_combinations.append(new_combo)
                else:
                    # Handle dynamic values like fromJson()
                    new_combo = combo.copy()
                    new_combo[key] = values
                    new_combinations.append(new_combo)
            combinations = new_combinations

        return combinations

    def analyze_workflow(self, filename: str, workflow: Dict):
        """Analyze a single workflow file."""
        workflow_name = workflow.get('name', filename)
        events = self.get_workflow_events(workflow)

        # Handle workflow_call separately
        on_config = workflow.get('on', workflow.get(True, {}))
        if isinstance(on_config, dict) and 'workflow_call' in on_config:
            self.analyze_called_workflow(filename, workflow)
            return

        jobs = workflow.get('jobs', {})

        for event in events:
            platforms = self.get_platforms_for_event(event)

            for job_name, job_config in jobs.items():
                # Check job-level conditions
                job_condition = job_config.get('if', '')
                if not self.evaluate_condition(job_condition, event, {}):
                    continue

                # Handle strategy matrix
                strategy = job_config.get('strategy', {})
                matrix_config = strategy.get('matrix', {})
                matrix_combinations = self.expand_matrix(matrix_config, platforms)

                steps = job_config.get('steps', [])

                for matrix_combo in matrix_combinations:
                    # Determine platform(s) for this matrix combination
                    if 'platform' in matrix_combo:
                        # Matrix job with platform - runs on ONE specific platform
                        platform_value = matrix_combo['platform']
                        if isinstance(platform_value, str):
                            actual_platforms = [platform_value]
                        else:
                            actual_platforms = ['linux/amd64']  # fallback
                    else:
                        # No platform matrix - this job runs on default runner (amd64)
                        # Jobs like prepare_build_vars, determine_platforms run on default runner
                        actual_platforms = ['linux/amd64']  # Default GitHub runner

                    for step in steps:
                        step_name = step.get('name', 'Unnamed step')
                        step_condition = step.get('if', '')

                        if not self.evaluate_condition(step_condition, event, matrix_combo):
                            continue

                        for actual_platform in actual_platforms:
                            amd64 = actual_platform == 'linux/amd64'
                            arm64 = actual_platform == 'linux/arm64'

                            execution = StepExecution(
                                workflow_file=filename,
                                workflow_name=workflow_name,
                                job_name=job_name,
                                step_name=step_name,
                                event=event,
                                amd64=amd64,
                                arm64=arm64,
                                condition=step_condition,
                                matrix_values=matrix_combo
                            )

                            self.step_executions.append(execution)

                # Handle workflow calls within jobs
                uses = job_config.get('uses', '')
                if uses and uses.startswith('./'):
                    self.analyze_workflow_call(filename, job_name, uses, event, platforms, job_config)

    def analyze_called_workflow(self, filename: str, workflow: Dict):
        """Analyze workflows that are called by other workflows."""
        # These will be processed when the calling workflow is analyzed
        pass

    def analyze_workflow_call(self, calling_file: str, calling_job: str, called_workflow: str, event: EventType, platforms: List[str], job_config: Dict):
        """Analyze a workflow call."""
        called_filename = called_workflow.replace('./', '').replace('.github/workflows/', '')
        if not called_filename.endswith('.yml'):
            called_filename += '.yml'

        if called_filename not in self.workflows:
            return

        called_workflow_config = self.workflows[called_filename]
        called_workflow_name = called_workflow_config.get('name', called_filename)

        # Get inputs passed to the called workflow
        with_inputs = job_config.get('with', {})

        # Analyze jobs in the called workflow
        jobs = called_workflow_config.get('jobs', {})

        for job_name, job_config in jobs.items():
            job_condition = job_config.get('if', '')
            if not self.evaluate_condition(job_condition, event, {}):
                continue

            strategy = job_config.get('strategy', {})
            matrix_config = strategy.get('matrix', {})
            matrix_combinations = self.expand_matrix(matrix_config, platforms)

            steps = job_config.get('steps', [])

            for matrix_combo in matrix_combinations:
                # Determine platform(s) for this matrix combination in called workflow
                if 'platform' in matrix_combo:
                    # Matrix job with platform - runs on ONE specific platform
                    platform_value = matrix_combo['platform']
                    if isinstance(platform_value, str):
                        actual_platforms = [platform_value]
                    else:
                        actual_platforms = ['linux/amd64']  # fallback
                else:
                    # No platform matrix - this job doesn't depend on platform
                    actual_platforms = ['linux/amd64']  # Default GitHub runner

                for step in steps:
                    step_name = step.get('name', 'Unnamed step')
                    step_condition = step.get('if', '')

                    if not self.evaluate_condition(step_condition, event, matrix_combo):
                        continue

                    for platform in actual_platforms:
                        amd64 = platform == 'linux/amd64'
                        arm64 = platform == 'linux/arm64'

                        execution = StepExecution(
                            workflow_file=f"{calling_file} → {called_filename}",
                            workflow_name=f"{called_workflow_name} (called)",
                            job_name=job_name,
                            step_name=step_name,
                            event=event,
                            amd64=amd64,
                            arm64=arm64,
                            condition=step_condition,
                            matrix_values=matrix_combo
                        )

                        self.step_executions.append(execution)

    def get_job_dependencies(self, workflow: Dict) -> Dict[str, List[str]]:
        """Parse job dependencies from workflow."""
        jobs = workflow.get('jobs', {})
        dependencies = {}

        for job_name, job_config in jobs.items():
            needs = job_config.get('needs', [])
            if isinstance(needs, str):
                needs = [needs]
            elif needs is None:
                needs = []
            dependencies[job_name] = needs

        return dependencies

    def topological_sort_jobs(self, dependencies: Dict[str, List[str]]) -> List[str]:
        """Sort jobs in execution order using topological sort."""
        # Calculate in-degree for each job
        in_degree = {job: 0 for job in dependencies.keys()}
        for job, deps in dependencies.items():
            for dep in deps:
                if dep in in_degree:
                    in_degree[job] += 1

        # Initialize queue with jobs that have no dependencies
        queue = [job for job, degree in in_degree.items() if degree == 0]
        result = []

        while queue:
            # Sort queue to ensure deterministic order for jobs at same level
            queue.sort()
            job = queue.pop(0)
            result.append(job)

            # Process jobs that depend on current job
            for dependent_job, deps in dependencies.items():
                if job in deps:
                    in_degree[dependent_job] -= 1
                    if in_degree[dependent_job] == 0:
                        queue.append(dependent_job)

        # Add any remaining jobs (in case of cycles, fallback to alphabetical)
        remaining = set(dependencies.keys()) - set(result)
        result.extend(sorted(remaining))

        return result

    def get_step_order(self, workflow_file: str, job_name: str) -> Dict[str, int]:
        """Get step execution order within a job."""
        if workflow_file not in self.workflows:
            return {}

        workflow = self.workflows[workflow_file]
        jobs = workflow.get('jobs', {})

        if job_name not in jobs:
            return {}

        steps = jobs[job_name].get('steps', [])
        step_order = {}

        for i, step in enumerate(steps):
            step_name = step.get('name', 'Unnamed step')
            step_order[step_name] = i

        return step_order

    def create_execution_order_key(self, execution: StepExecution) -> Tuple:
        """Create a sorting key for execution order."""
        # Get workflow file base name for sorting
        workflow_base = execution.workflow_file.split(' → ')[0]

        # Get job dependencies if available
        job_order = 0
        if workflow_base in self.workflows:
            dependencies = self.get_job_dependencies(self.workflows[workflow_base])
            sorted_jobs = self.topological_sort_jobs(dependencies)
            try:
                job_order = sorted_jobs.index(execution.job_name)
            except ValueError:
                job_order = 999  # Put unknown jobs at end

        # Get step order within job
        step_order = 0
        step_orders = self.get_step_order(workflow_base, execution.job_name)
        if execution.step_name in step_orders:
            step_order = step_orders[execution.step_name]

        # Event type ordering (some events are more common/important)
        event_priority = {
            EventType.PUSH_MASTER: 0,
            EventType.PULL_REQUEST: 1,
            EventType.MERGE_GROUP: 2,
            EventType.RELEASE: 3,
            EventType.WORKFLOW_DISPATCH_BOTH: 4,
            EventType.WORKFLOW_DISPATCH_AMD64_ONLY: 5,
            EventType.WORKFLOW_DISPATCH_ARM64_ONLY: 6,
        }

        event_order = event_priority.get(execution.event, 999)

        # Platform ordering (amd64 before arm64)
        platform_order = 0 if execution.amd64 else 1

        return (
            workflow_base,           # Workflow file
            job_order,              # Job dependency order
            step_order,             # Step order within job
            event_order,            # Event priority
            platform_order          # Platform order
        )

    def generate_truth_table(self) -> str:
        """Generate the markdown truth table with deduplication and execution ordering."""
        lines = [
            "# GitHub Actions Workflow Execution Truth Table",
            "",
            "This table shows which steps execute on which platforms for different trigger events.",
            "",
            "## Legend",
            "- ✅ = Step executes on this platform",
            "- ❌ = Step does not execute on this platform",
            "- Event types:",
            "  - `push_master`: Push to master branch",
            "  - `pull_request`: Pull request events",
            "  - `merge_group`: Merge group events",
            "  - `release`: Release published",
            "  - `workflow_dispatch_*`: Manual workflow dispatch with different platform selections",
            "",
            "| Workflow File | Workflow Name | Job | Step | Event | amd64 | arm64 | Condition |",
            "|---|---|---|---|---|---|---|---|"
        ]

        # First, group executions by everything except daemon to combine daemon variants
        daemon_grouped = {}
        for execution in self.step_executions:
            matrix_without_daemon = {}
            daemon_values = []

            if execution.matrix_values:
                for k, v in execution.matrix_values.items():
                    if k == 'daemon':
                        if isinstance(v, dict) and 'name' in v:
                            daemon_values.append(v['name'])
                        else:
                            daemon_values.append(str(v))
                    else:
                        matrix_without_daemon[k] = v

            group_key = (
                execution.workflow_file,
                execution.workflow_name,
                execution.job_name,
                execution.step_name,
                execution.event.value,
                execution.condition,
                tuple(sorted(matrix_without_daemon.items()))
            )

            if group_key not in daemon_grouped:
                daemon_grouped[group_key] = {
                    'execution': execution,
                    'amd64': execution.amd64,
                    'arm64': execution.arm64,
                    'daemons': set(),
                    'matrix_without_daemon': matrix_without_daemon
                }
            else:
                daemon_grouped[group_key]['amd64'] = daemon_grouped[group_key]['amd64'] or execution.amd64
                daemon_grouped[group_key]['arm64'] = daemon_grouped[group_key]['arm64'] or execution.arm64

            daemon_grouped[group_key]['daemons'].update(daemon_values)

        # Next, group by execution pattern (everything except event) to find duplicates
        pattern_groups = defaultdict(list)
        for group_key, group_data in daemon_grouped.items():
            execution = group_data['execution']

            # Create pattern key (everything except event)
            pattern_key = (
                execution.workflow_file,
                execution.workflow_name,
                execution.job_name,
                execution.step_name,
                group_data['amd64'],
                group_data['arm64'],
                execution.condition,
                tuple(sorted(group_data['matrix_without_daemon'].items())),
                tuple(sorted(group_data['daemons']))
            )

            pattern_groups[pattern_key].append((group_key, group_data))

        # Create consolidated executions
        consolidated = []
        for pattern_key, pattern_instances in pattern_groups.items():
            if len(pattern_instances) == 1:
                # No duplication, keep as is
                group_key, group_data = pattern_instances[0]
                consolidated.append(group_data)
            else:
                # Multiple events with same pattern - consolidate
                events = [instance['execution'].event for _, instance in pattern_instances]
                events.sort(key=lambda e: e.value)

                # Use first instance as base, but update event list
                _, base_data = pattern_instances[0]
                consolidated_data = base_data.copy()

                # Create consolidated event string
                event_names = [e.value for e in events]
                if len(event_names) > 3:
                    consolidated_data['event_str'] = f"{event_names[0]}, ... (+{len(event_names)-1} more)"
                else:
                    consolidated_data['event_str'] = ", ".join(event_names)

                consolidated.append(consolidated_data)

        # Sort by execution order
        consolidated.sort(key=lambda x: self.create_execution_order_key(x['execution']))

        # Final step: Platform coalescing with OR logic
        platform_groups = defaultdict(list)
        for group_data in consolidated:
            execution = group_data['execution']

            # Create platform-agnostic key (remove platform from matrix)
            matrix_without_platform = {}
            for k, v in group_data['matrix_without_daemon'].items():
                if k != 'platform':
                    matrix_without_platform[k] = v

            # Group by everything except platform and architecture execution
            platform_key = (
                execution.workflow_file,
                execution.workflow_name,
                execution.job_name,
                execution.step_name,
                execution.condition,
                tuple(sorted(matrix_without_platform.items())),
                tuple(sorted(group_data['daemons']))
            )

            platform_groups[platform_key].append(group_data)

        # Consolidate platform groups with OR logic
        final_consolidated = []
        for platform_key, platform_instances in platform_groups.items():
            if len(platform_instances) == 1:
                # No platform variants, keep as is but remove platform from matrix
                group_data = platform_instances[0].copy()
                # Remove platform from matrix_without_daemon
                matrix_without_platform = {}
                for k, v in group_data['matrix_without_daemon'].items():
                    if k != 'platform':
                        matrix_without_platform[k] = v
                group_data['matrix_without_daemon'] = matrix_without_platform
                final_consolidated.append(group_data)
            else:
                # Multiple platform variants - apply OR logic
                base_data = platform_instances[0].copy()

                # OR logic for architectures
                combined_amd64 = any(instance['amd64'] for instance in platform_instances)
                combined_arm64 = any(instance['arm64'] for instance in platform_instances)

                # Combine all events from all platform variants
                all_events = set()
                for instance in platform_instances:
                    if 'event_str' in instance:
                        # Parse consolidated event string
                        event_str = instance['event_str']
                        if ', ... (+' in event_str:
                            # Extract first event and approximate count
                            first_event = event_str.split(',')[0]
                            all_events.add(first_event)
                            # For now, we'll mark this as having more events
                            # In a real implementation, we'd track all events properly
                        else:
                            # Simple comma-separated events
                            events = [e.strip() for e in event_str.split(',')]
                            all_events.update(events)
                    else:
                        all_events.add(instance['execution'].event.value)

                # Remove platform from matrix
                matrix_without_platform = {}
                for k, v in base_data['matrix_without_daemon'].items():
                    if k != 'platform':
                        matrix_without_platform[k] = v

                # Create consolidated platform group
                consolidated_platform_data = {
                    'execution': base_data['execution'],
                    'amd64': combined_amd64,
                    'arm64': combined_arm64,
                    'daemons': base_data['daemons'],
                    'matrix_without_daemon': matrix_without_platform
                }

                # Create consolidated event string
                sorted_events = sorted(list(all_events))
                if len(sorted_events) > 3:
                    consolidated_platform_data['event_str'] = f"{sorted_events[0]}, ... (+{len(sorted_events)-1} more)"
                else:
                    consolidated_platform_data['event_str'] = ", ".join(sorted_events)

                final_consolidated.append(consolidated_platform_data)

        # Sort final results by execution order
        final_consolidated.sort(key=lambda x: self.create_execution_order_key(x['execution']))

        # Generate output lines
        for group_data in final_consolidated:
            execution = group_data['execution']

            # Build matrix string
            matrix_items = []
            for k, v in group_data['matrix_without_daemon'].items():
                if isinstance(v, dict) and 'name' in v:
                    matrix_items.append(f"{k}={v['name']}")
                else:
                    matrix_items.append(f"{k}={v}")

            if group_data['daemons']:
                daemon_list = sorted(list(group_data['daemons']))
                matrix_items.append(f"daemon={','.join(daemon_list)}")

            matrix_str = ", ".join(matrix_items)

            amd64_symbol = "✅" if group_data['amd64'] else "❌"
            arm64_symbol = "✅" if group_data['arm64'] else "❌"

            condition_str = execution.condition[:50] + "..." if len(execution.condition) > 50 else execution.condition

            # Use consolidated event string if available
            event_str = group_data.get('event_str', execution.event.value)

            line = f"| `{execution.workflow_file}` | {execution.workflow_name} | `{execution.job_name}` | {execution.step_name} | `{event_str}` | {amd64_symbol} | {arm64_symbol} | {condition_str} |"
            lines.append(line)

        return "\n".join(lines)

    def run(self):
        """Main execution method."""
        self.load_workflows()

        for filename, workflow in self.workflows.items():
            print(f"Analyzing {filename}:")
            events = self.get_workflow_events(workflow)
            print(f"  Events: {[e.value for e in events]}")
            self.analyze_workflow(filename, workflow)

        truth_table = self.generate_truth_table()

        with open('ACTIONS.md', 'w') as f:
            f.write(truth_table)

        print(f"Generated truth table with {len(self.step_executions)} step executions")
        print("Output written to ACTIONS.md")

if __name__ == "__main__":
    analyzer = WorkflowAnalyzer()
    analyzer.run()
