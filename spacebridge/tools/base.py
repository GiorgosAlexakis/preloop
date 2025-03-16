"""Base classes for MCP tools in SpaceBridge."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, Type, TypeVar

from pydantic import BaseModel, Field, create_model

# TypeVar for tool implementations
T = TypeVar("T", bound="MCPTool")


class MCPToolMetadata(BaseModel):
    """Metadata about an MCP tool."""

    name: str = Field(..., description="Tool name")
    description: str = Field(..., description="Tool description")
    required_parameters: Set[str] = Field(
        default_factory=set, description="Required parameters for the tool"
    )
    optional_parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Optional parameters with default values"
    )


class MCPTool(ABC):
    """Base class for all MCP tools.

    All tools should inherit from this class and implement the execute method.
    """

    @classmethod
    @abstractmethod
    def metadata(cls) -> MCPToolMetadata:
        """Get metadata about the tool.

        Returns:
            MCPToolMetadata: Tool metadata.
        """
        pass

    @classmethod
    def parameter_model(cls) -> Type[BaseModel]:
        """Dynamically create a Pydantic model for the tool's parameters.

        Returns:
            Type[BaseModel]: A Pydantic model for validating the tool's parameters.
        """
        meta = cls.metadata()
        fields = {}

        # Add required parameters
        for param in meta.required_parameters:
            fields[param] = (Any, ...)

        # Add optional parameters with defaults
        for param, default in meta.optional_parameters.items():
            fields[param] = (Any, default)

        # Create and return the model
        return create_model(
            f"{meta.name.title()}Parameters",
            **fields,
            __doc__=f"Parameters for {meta.name}",
        )

    @abstractmethod
    def execute(self, parameters: Dict[str, Any]) -> Any:
        """Execute the tool with the given parameters.

        Args:
            parameters: The parameters to execute the tool with.

        Returns:
            The tool execution result.
        """
        pass

    def validate_parameters(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Validate the parameters against the tool's parameter schema.

        Args:
            parameters: The parameters to validate.

        Returns:
            The validated parameters.

        Raises:
            ValidationError: If the parameters are invalid.
        """
        # Get the parameter model for this tool
        model = self.parameter_model()

        # Validate and return the parameters
        return model(**parameters).model_dump()
