import React, { useContext } from "react";
import AuthContext from "../auth/AuthContext";

const Profile = () => {
  const { user } = useContext(AuthContext);
  const apiUrl = process.env.REACT_APP_API_URL;

  const handleSpotifyAuth = () => {
    window.location.href = apiUrl+"/spotify/login";
  };
  const isTokenExpired = (expiresAt) => {
    if (!expiresAt) return true;
    return new Date(expiresAt) <= new Date();
  };

  return (
    <div>
      <h2>Profile</h2>
      {user ? (
        <pre>{JSON.stringify(user, null, 2)}</pre>
      ) : (
        <p>No user data available.</p>
      )}

      {(!user?.spotify_token || isTokenExpired(user.spotify_token.expires_at)) && (
        <button onClick={handleSpotifyAuth}>
          {user?.spotify_token ? "Re-link Spotify" : "Link Spotify Account"}
        </button>
      )}
    </div>
  );
};

export default Profile;
