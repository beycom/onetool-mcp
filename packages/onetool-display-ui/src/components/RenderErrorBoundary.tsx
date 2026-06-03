import { Component, type ErrorInfo, type ReactNode } from "react";

interface RenderErrorBoundaryProps {
  children: ReactNode;
  label: string;
}

interface RenderErrorBoundaryState {
  error: Error | null;
}

export class RenderErrorBoundary extends Component<RenderErrorBoundaryProps, RenderErrorBoundaryState> {
  state: RenderErrorBoundaryState = { error: null };

  static getDerivedStateFromError(error: Error): RenderErrorBoundaryState {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error(`Display renderer failed for ${this.props.label}`, error, info);
  }

  componentDidUpdate(previousProps: RenderErrorBoundaryProps) {
    if (previousProps.label !== this.props.label && this.state.error) {
      this.setState({ error: null });
    }
  }

  render() {
    if (this.state.error) {
      return (
        <div className="renderer-error" role="alert">
          <strong>Preview unavailable</strong>
          <span>{this.state.error.message}</span>
        </div>
      );
    }
    return this.props.children;
  }
}
