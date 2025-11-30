import React, {createContext, useContext, useEffect, useState} from 'react';

// Define the shape of the key state context
export interface KeyStatesContextType {
  shiftKey: boolean;
  ctrlKey: boolean;
  altKey: boolean;
}

// Create the context
export const KeyStatesContext = createContext<KeyStatesContextType | undefined>(undefined);

// Custom hook to use the KeyStatesContext
export const useKeyStates = () => {
  const context = useContext(KeyStatesContext);
  if (context === undefined) {
    throw new Error('useKeyStates must be used within a KeyStatesProvider');
  }
  return context;
};

// KeyStatesProvider component
export const KeyStatesProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [shiftKey, setShiftKey] = useState(false);
  const [ctrlKey, setCtrlKey] = useState(false);
  const [altKey, setAltKey] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Shift') setShiftKey(true);
      if (e.key === 'Control') setCtrlKey(true);
      if (e.key === 'Alt') setAltKey(true);
    };

    const handleKeyUp = (e: KeyboardEvent) => {
      if (e.key === 'Shift') setShiftKey(false);
      if (e.key === 'Control') setCtrlKey(false);
      if (e.key === 'Alt') setAltKey(false);
    };

    window.addEventListener('keydown', handleKeyDown);
    window.addEventListener('keyup', handleKeyUp);

    return () => {
      window.removeEventListener('keydown', handleKeyDown);
      window.removeEventListener('keyup', handleKeyUp);
    };
  }, []);

  return (
    <KeyStatesContext.Provider value={{ shiftKey, ctrlKey, altKey }}>
      {children}
    </KeyStatesContext.Provider>
  );
};
