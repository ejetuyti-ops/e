using System;
using System.Windows.Forms;

namespace EJET.Browser;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        ApplicationConfiguration.Initialize();
        Application.Run(new BrowserForm());
    }
}