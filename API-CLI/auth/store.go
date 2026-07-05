package auth

//////////////////////////
//   Import Libraries   //
//////////////////////////
import (
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"path/filepath"
)

//////////////////////////
//      Structures      //
//////////////////////////
type Credentials struct {
	Username  string `json:"username"`
	Token     string `json:"token,omitempty"`
	SourceURL string `json:"source_url,omitempty"`
}

//////////////////////////
//   Helper Functions   //
//////////////////////////
func credsPath() (string, error) {
	home, err := os.UserHomeDir()
	if err != nil {
		return "", err
	}
	dir := filepath.Join(home, ".api-cli")
	if err := os.MkdirAll(dir, 0755); err != nil {
		return "", err
	}
	return filepath.Join(dir, "credentials.json"), nil
}

//////////////////////////
//   Public Functions   //
//////////////////////////
func Save(creds Credentials) error {
	path, err := credsPath()
	if err != nil {
		return err
	}
	data, err := json.MarshalIndent(creds, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0600)
}

func Load() (Credentials, error) {
	var creds Credentials
	path, err := credsPath()
	if err != nil {
		return creds, err
	}
	data, err := os.ReadFile(path)
	if err != nil {
		if errors.Is(err, os.ErrNotExist) {
			return creds, fmt.Errorf("no se encontraron credenciales guardadas. Ejecuta 'login' primero")
		}
		return creds, err
	}
	err = json.Unmarshal(data, &creds)
	return creds, err
}

func Clear() error {
	path, err := credsPath()
	if err != nil {
		return err
	}
	err = os.Remove(path)
	if err != nil && !errors.Is(err, os.ErrNotExist) {
		return err
	}
	return nil
}
