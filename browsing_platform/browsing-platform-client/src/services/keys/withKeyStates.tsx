import React from 'react';
import { KeyStatesContext, KeyStatesContextType } from './keyStates';

function withKeyStates<P extends KeyStatesContextType>(Component: React.ComponentType<P>) {
  return function KeyStatesComponent(props: Omit<P, keyof KeyStatesContextType>) {
    return (
      <KeyStatesContext.Consumer>
        {(context) => {
          if (context === undefined) {
            throw new Error('withKeyStates must be used within a KeyStatesProvider');
          }
          return <Component {...(props as P)} {...context} />;
        }}
      </KeyStatesContext.Consumer>
    );
  };
}

export default withKeyStates;