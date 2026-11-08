import React from 'react';

export const Footer: React.FC = () => {
  return (
    <footer className="footer" role="contentinfo">
      <p>
        <strong>⚠️ Fictional Training Project</strong>: For educational purposes only. Does not connect to real banks, lenders, or credit bureaus.
      </p>
      <p style={{ marginTop: '0.25rem', color: '#94a3b8' }}>
        Mini Loan Marketplace &copy; {new Date().getFullYear()}
      </p>
    </footer>
  );
};
