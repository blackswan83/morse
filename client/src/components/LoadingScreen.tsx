export function LoadingScreen() {
  return (
    <div className="h-full flex items-center justify-center bg-morse-950">
      <div className="text-center">
        <div className="relative w-16 h-16 mx-auto mb-4">
          <div className="absolute inset-0 border-4 border-morse-600/30 rounded-full"></div>
          <div className="absolute inset-0 border-4 border-morse-500 rounded-full border-t-transparent animate-spin"></div>
        </div>
        <p className="text-morse-400">Initializing secure environment...</p>
      </div>
    </div>
  );
}
