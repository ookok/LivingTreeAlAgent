"""
Seamless Tool Integration Demo

Demonstrates how to use the seamless_tool_integration module
for seamless air quality prediction.

Run:
    cd d:/mhzyapp/hermes-desktop
    python core/seamless_tool_integration/examples/demo.py
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def demo_model_deployer():
    """Demo: Model Deployer"""
    print("\n" + "=" * 60)
    print("Demo 1: Model Deployer")
    print("=" * 60)

    from client.src.business.seamless_tool_integration.model_deployer import (
        ModelDeployer, ToolType, DeploymentStatus
    )

    deployer = ModelDeployer()

    # Get all available tools
    print("\nAvailable tools:")
    for tool in deployer.get_all_tools():
        status = "[READY]" if tool.is_installed else "[NOT INSTALLED]"
        print("  - {}: {}".format(tool.name, status))
        print("    Version: {}".format(tool.version))
        print("    Type: {}".format(tool.tool_type.value))
        print("    Description: {}".format(tool.description))

    # Check specific tool
    print("\nCheck AERMOD status:")
    ready = deployer.is_tool_ready("aermod")
    print("  AERMOD ready: {}".format("Yes" if ready else "No"))

    # Check dependencies
    print("\nCheck dependencies:")
    deps = deployer.check_dependencies("aermod")
    for dep, status in deps.items():
        print("  {}: {}".format(dep, "OK" if status else "NOT MET"))


def demo_input_generator():
    """Demo: Input Generator"""
    print("\n" + "=" * 60)
    print("Demo 2: Input Generator")
    print("=" * 60)

    from client.src.business.seamless_tool_integration.input_generator import (
        InputGenerator, ProjectData, SourceParams,
        MeteorologyData, ReceptorGrid, ScaleType
    )
    import tempfile

    # Create project data
    project = ProjectData(
        project_name="Nanjing Chemical Industrial Park",
        project_id="NJHG2024",
        latitude=32.04,
        longitude=118.78,
        location_name="Nanjing Chemical Industrial Park",
        scale=ScaleType.LOCAL,
        pollutants=["SO2", "NO2", "PM10", "PM25"],
        land_use="INDUSTRIAL",
        terrain_type="FLAT"
    )

    # Add emission sources
    project.emission_sources = [
        SourceParams(
            source_id="S1",
            source_name="Main Stack",
            latitude=32.04,
            longitude=118.78,
            source_type="POINT",
            emission_rate=5.0,        # g/s
            stack_height=50.0,       # m
            stack_diameter=2.0,       # m
            exit_velocity=10.0,       # m/s
            exit_temperature=400      # K
        ),
        SourceParams(
            source_id="S2",
            source_name="Backup Stack",
            latitude=32.041,
            longitude=118.781,
            source_type="POINT",
            emission_rate=2.0,
            stack_height=40.0,
            stack_diameter=1.5,
            exit_velocity=8.0,
            exit_temperature=380
        )
    ]

    # Set receptor grid
    project.receptor_grid = ReceptorGrid(
        center_x=0,
        center_y=0,
        x_min=-5000,
        x_max=5000,
        y_min=-5000,
        y_max=5000,
        x_step=100,
        y_step=100
    )

    # Set meteorology data
    project.meteorology = MeteorologyData(
        station_id="58362",
        station_name="Nanjing Weather Station",
        data_year=2024
    )

    print("\nProject: {}".format(project.project_name))
    print("  Location: ({}, {})".format(project.latitude, project.longitude))
    print("  Scale: {}".format(project.scale.value))
    print("  Pollutants: {}".format(", ".join(project.pollutants)))
    print("  Emission sources: {}".format(len(project.emission_sources)))
    print("  Evaluation points: {}".format(project.receptor_grid.total_points))

    # Generate input files
    output_dir = tempfile.mkdtemp(prefix="aermod_input_")
    print("\nGenerating input files to: {}".format(output_dir))

    generator = InputGenerator.create("aermod", project)
    files = generator.generate(output_dir)

    print("\nGenerated files:")
    for file_type, file_path in files.items():
        size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
        print("  {}: {} ({} bytes)".format(file_type, file_path, size))

    # Show main input file preview
    if 'input' in files and os.path.exists(files['input']):
        print("\nInput file preview:")
        print("-" * 40)
        with open(files['input'], 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.split('\n')[:25]
            for line in lines:
                print(line)
            if len(content.split('\n')) > 25:
                print("... (more content omitted)")


def demo_tool_executor():
    """Demo: Tool Executor"""
    print("\n" + "=" * 60)
    print("Demo 3: Tool Executor")
    print("=" * 60)

    from client.src.business.seamless_tool_integration.tool_executor import (
        ToolExecutor, ExecutionStatus
    )

    executor = ToolExecutor()

    # Add execution steps
    executor.add_step("prepare", "Prepare Environment", "Check tools and dependencies")
    executor.add_step("input", "Generate Input", "Create input files")
    executor.add_step("run", "Run Model", "Execute AERMOD calculation")
    executor.add_step("parse", "Parse Results", "Extract concentration data")

    print("\nExecution steps:")
    for step in executor.get_all_steps():
        print("  {}: {} - {}".format(step.step_id, step.name, step.description))

    # Simulate execution
    print("\nSimulating execution:")

    def on_progress(step):
        status_icon = {
            ExecutionStatus.PENDING: "[PENDING]",
            ExecutionStatus.RUNNING: "[RUNNING]",
            ExecutionStatus.COMPLETED: "[DONE]",
            ExecutionStatus.FAILED: "[FAILED]"
        }
        icon = status_icon.get(step.status, "[UNKNOWN]")
        print("  {} {}: {:.0f}%".format(icon, step.name, step.progress))

    executor.set_progress_callback(on_progress)

    # Execute steps
    executor._start_step("prepare")
    for i in range(101):
        executor._set_step_progress(i, "Preparing... {}%".format(i))
    executor._finish_step("prepare")

    executor._start_step("input")
    for i in range(101):
        executor._set_step_progress(i)
    executor._finish_step("input")

    executor._start_step("run")
    for i in range(101):
        executor._set_step_progress(i)
    executor._finish_step("run")

    executor._start_step("parse")
    for i in range(101):
        executor._set_step_progress(i)
    executor._finish_step("parse")


def demo_result_parser():
    """Demo: Result Parser"""
    print("\n" + "=" * 60)
    print("Demo 4: Result Parser")
    print("=" * 60)

    from client.src.business.seamless_tool_integration.result_parser import (
        ResultParser, PredictionResult, ConcentrationData,
        MaxResult, ReportGenerator
    )

    # Create mock result
    result = PredictionResult(
        project_name="Nanjing Chemical Industrial Park",
        tool_type="aermod"
    )

    # Add concentration data
    import random
    for i in range(-50, 51):
        for j in range(-50, 51):
            distance = (i**2 + j**2) ** 0.5
            concentration = 100 * (1 - distance / 50) + random.uniform(-5, 5)
            concentration = max(0, concentration)

            result.concentration_grid.append(ConcentrationData(
                x=float(i * 100),
                y=float(j * 100),
                concentration=concentration
            ))

    # Add max results
    result.max_results = [
        MaxResult(
            pollutant="SO2",
            max_type="1H",
            value=85.5,
            x=0, y=0,
            exceedance_ratio=0,
            is_exceedance=False
        ),
        MaxResult(
            pollutant="NO2",
            max_type="1H",
            value=125.3,
            x=100, y=100,
            exceedance_ratio=0,
            is_exceedance=False
        ),
        MaxResult(
            pollutant="PM25",
            max_type="24H",
            value=165.0,
            x=-100, y=200,
            exceedance_ratio=2.2,
            is_exceedance=True
        )
    ]

    # Statistics
    result.statistics = {
        "total_points": len(result.concentration_grid),
        "mean": 35.2,
        "max": 125.3,
        "min": 0.1,
        "std": 28.5,
        "percentile_95": 95.0,
        "percentile_99": 110.0
    }

    print("\nPrediction Result: {}".format(result.project_name))
    print("  Tool: {}".format(result.tool_type.upper()))
    print("  Evaluation points: {}".format(result.statistics['total_points']))
    print("  Max concentration: {:.2f} ug/m3".format(result.statistics['max']))
    print("  Average concentration: {:.2f} ug/m3".format(result.statistics['mean']))
    print("  Exceedance points: {}".format(result.exceedance_count))

    print("\nMax concentration by pollutant:")
    for max_r in result.max_results:
        status = "[EXCEEDANCE]" if max_r.is_exceedance else "[OK]"
        print("  {} ({}): {:.2f} ug/m3 - {}".format(
            max_r.pollutant, max_r.max_type, max_r.value, status))

    # Generate report
    print("\n" + "-" * 40)
    print("Auto-generated Analysis Report:")
    print("-" * 40)

    generator = ReportGenerator(result)
    report = generator.generate_text_report()
    print(report)


def demo_cloud_bridge():
    """Demo: Cloud Bridge"""
    print("\n" + "=" * 60)
    print("Demo 5: Cloud Bridge")
    print("=" * 60)

    from client.src.business.seamless_tool_integration.cloud_bridge import (
        CloudBridge, CloudExecutionMode, LocalCapabilityDetector
    )

    bridge = CloudBridge()

    # Detect local capability
    print("\nDetecting local computing capability:")
    capability = bridge.detect_local_capability()

    print("  OS: {}".format(capability['os']))
    print("  CPU cores: {} (logical: {})".format(
        capability['cpu_count'], capability['cpu_count_logical']))
    print("  CPU usage: {:.1f}%".format(capability['cpu_percent']))
    print("  Total memory: {:.1f} GB".format(capability['memory_total_gb']))
    print("  Available memory: {:.1f} GB".format(capability['memory_available_gb']))
    print("  GPU available: {}".format("Yes" if capability['gpu']['available'] else "No"))
    if capability['gpu']['available']:
        print("    Model: {}".format(capability['gpu']['name']))
    print("  Overall score: {:.0f}/100".format(capability['capability_score']))

    # Determine cloud usage
    print("\nExecution plan decision:")
    should_cloud = bridge.should_use_cloud("aermod", CloudExecutionMode.AUTO, 30)
    print("  AERMOD (30 min): {}".format("CLOUD" if should_cloud else "LOCAL"))

    should_cloud = bridge.should_use_cloud("calpuff", CloudExecutionMode.AUTO, 60)
    print("  CALPUFF (60 min): {}".format("CLOUD" if should_cloud else "LOCAL"))

    # Cost estimation
    print("\nCloud cost estimation:")
    for tool in ["aermod", "calpuff", "pyspray"]:
        cost = bridge.estimate_cost(tool, 30)
        print("  {}: {:.2f}/30 min".format(tool, cost))


def demo_manager():
    """Demo: Integration Manager"""
    print("\n" + "=" * 60)
    print("Demo 6: Integration Manager")
    print("=" * 60)

    from client.src.business.seamless_tool_integration.manager import SeamlessIntegrationManager

    # Get manager instance
    manager = SeamlessIntegrationManager.get_instance()
    print("\nManager instance: {}".format(id(manager)))

    # Check tool status
    print("\nTool readiness check:")
    ready = manager.check_tool_ready("aermod")
    print("  AERMOD: {}".format("[READY]" if ready else "[NOT READY]"))

    # Local capability
    print("\nLocal capability assessment:")
    cap = manager.get_local_capability()
    print("  Score: {}/100".format(cap['capability_score']))

    print("\nManager features:")
    print("  - check_tool_ready() - Check tool status")
    print("  - ensure_tool_ready() - Ensure tool is installed")
    print("  - run_prediction() - One-click prediction")
    print("  - get_visualization() - Get visualization tools")
    print("  - generate_report() - Generate analysis report")
    print("  - export_results() - Export all results")


def main():
    """Main function"""
    print("""
================================================================
       Seamless Tool Integration - Air Prediction Demo
       Core Concept: One click does everything
================================================================
    """)

    try:
        demo_model_deployer()
        demo_input_generator()
        demo_tool_executor()
        demo_result_parser()
        demo_cloud_bridge()
        demo_manager()

        print("\n" + "=" * 60)
        print("Demo Complete!")
        print("=" * 60)
        print("""
Next steps:
1. Start UI panel: python ui/air_prediction_panel.py
2. Configure project parameters
3. Click "Start Prediction"
4. View results and visualization
        """)

    except ImportError as e:
        print("\n[ERROR] Import error: {}".format(e))
        print("Please ensure all dependencies are installed:")
        print("  pip install numpy matplotlib PyQt6")
    except Exception as e:
        print("\n[ERROR] Demo failed: {}".format(e))
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
