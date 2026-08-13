from setuptools import find_packages, setup


package_name = "vla_manipulator_runtime"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="VLA Intern Sprint",
    maintainer_email="local@example.com",
    description="Franka ROS 2 runtime checks and observation snapshot adapter.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "franka_joint_command_test = vla_manipulator_runtime.franka_joint_command_test:main",
            "observation_adapter_node = vla_manipulator_runtime.observation_adapter_node:main",
        ],
    },
)
